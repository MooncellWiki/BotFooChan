"""插件配置段：看、改，以及某个字段的修改历史（提示词页用）"""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Query
from nonebot_plugin_orm import get_session
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from src.plugins.webui.auth import CurrentAdmin
from src.providers import settings
from src.providers.settings import AuditLog, NotPersistentError, Section, UnknownSecret
from src.providers.settings.fields import flagged

from .common import actor, aware, bad_request, invalid, not_found, unavailable

router = APIRouter(prefix="/settings", tags=["settings"])


class SectionSummary(BaseModel):
    key: str
    title: str
    description: str
    source: Literal["env", "database"]
    """当前生效的值来自哪里"""
    updated_at: datetime | None
    updated_by: str | None
    restart_fields: list[str]
    """改了要重启才生效的字段"""


class SectionDetail(SectionSummary):
    json_schema: dict[str, Any]
    value: dict[str, Any]
    """当前值，密钥打码；原样提交回来表示不改"""
    editable: bool
    """能不能改（配置没从库里加载时只读）"""


def _summary(section: Section) -> SectionSummary:
    return SectionSummary(
        key=section.key,
        title=section.title,
        description=section.description,
        source=section.source,
        updated_at=aware(section.updated_at) if section.updated_at else None,
        updated_by=section.updated_by,
        restart_fields=flagged(section.model, "restart"),
    )


def _detail(section: Section) -> SectionDetail:
    return SectionDetail(
        **_summary(section).model_dump(),
        json_schema=section.model.model_json_schema(by_alias=False),
        value=section.masked(),
        editable=settings.persistent(),
    )


def get_or_404(key: str) -> Section:
    try:
        return settings.get_section(key)
    except KeyError:
        raise not_found(f"配置段 {key} ") from None


async def save_section(
    key: str, data: dict[str, Any], admin_actor: str, prefix: tuple[str | int, ...] = ()
) -> None:
    """保存并把各类错误转成接口错误"""
    try:
        await settings.save(key, data, actor=admin_actor)
    except NotPersistentError as e:
        raise unavailable(str(e)) from e
    except ValidationError as e:
        raise invalid(e, prefix) from e
    except UnknownSecret as e:
        raise bad_request(str(e)) from e


@router.get("")
async def list_settings() -> list[SectionSummary]:
    """所有配置段"""
    return [_summary(s) for s in settings.sections()]


@router.get("/{key}")
async def get_settings(key: str) -> SectionDetail:
    """一个配置段的 schema 和当前值"""
    return _detail(get_or_404(key))


@router.put("/{key}")
async def put_settings(
    key: str, body: Annotated[dict[str, Any], Body()], admin: CurrentAdmin
) -> SectionDetail:
    """整段保存"""
    section = get_or_404(key)
    await save_section(key, body, actor(admin))
    return _detail(section)


class HistoryEntry(BaseModel):
    id: int
    at: datetime
    actor: str
    action: str
    changes: dict[str, list[Any]]
    """{点分路径: [旧值, 新值]}，密钥打码"""


@router.get("/{key}/history")
async def get_settings_history(
    key: str,
    path: Annotated[str | None, Query(description="只看这个字段（点分路径）")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[HistoryEntry]:
    """配置段的修改历史，新的在前"""
    get_or_404(key)
    async with get_session() as session:
        rows = (
            await session.scalars(
                select(AuditLog)
                .where(AuditLog.entity == f"settings:{key}")
                .order_by(AuditLog.id.desc())
                .limit(500 if path else limit)
            )
        ).all()
    entries: list[HistoryEntry] = []
    for row in rows:
        changes: dict[str, list[Any]] = row.detail.get("changes") or {}
        if path is not None:
            changes = {
                k: v
                for k, v in changes.items()
                if k == path or k.startswith(path + ".")
            }
            if not changes:
                continue
        entries.append(
            HistoryEntry(
                id=row.id,
                at=aware(row.at),
                actor=row.actor,
                action=row.action,
                changes=changes,
            )
        )
        if len(entries) >= limit:
            break
    return entries
