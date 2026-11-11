"""管理员名单和审计记录"""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from nonebot_plugin_orm import get_session
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from src.plugins.webui import admins as admin_store
from src.plugins.webui.auth import CurrentAdmin
from src.plugins.webui.config import webui_config
from src.providers.settings import AuditLog

from .common import Page, actor, aware, conflict, not_found

router = APIRouter(tags=["admin"])


class AdminOut(BaseModel):
    login: str
    source: Literal["env", "database"]
    """env 的写在 WEBUI__ADMINS 里，页面上删不掉"""
    note: str = ""
    added_by: str | None = None
    added_at: datetime | None = None


@router.get("/admins")
async def list_admins() -> list[AdminOut]:
    """管理员名单"""
    out = [AdminOut(login=login, source="env") for login in sorted(webui_config.admins)]
    out += [
        AdminOut(
            login=row.login,
            source="database",
            note=row.note,
            added_by=row.added_by,
            added_at=aware(row.added_at),
        )
        for row in await admin_store.list_admins()
        if row.login not in webui_config.admins
    ]
    return out


class AdminIn(BaseModel):
    login: str = Field(min_length=1, max_length=39, pattern=r"^[A-Za-z0-9-]+$")
    """GitHub 用户名"""
    note: str = Field(default="", max_length=256)


@router.post("/admins")
async def add_admin(body: AdminIn, admin: CurrentAdmin) -> list[AdminOut]:
    """添加管理员"""
    login = body.login.lower()
    if login in webui_config.admins or login in admin_store.db_admins():
        raise conflict(f"{body.login} 已经是管理员了")
    await admin_store.add_admin(login, body.note, actor(admin))
    return await list_admins()


@router.delete("/admins/{login}")
async def remove_admin(login: str, admin: CurrentAdmin) -> list[AdminOut]:
    """移除管理员（.env 里的删不掉）"""
    login = login.lower()
    if login in webui_config.admins:
        raise conflict(f"{login} 写在 .env 的 WEBUI__ADMINS 里，要在那里删")
    if not await admin_store.remove_admin(login, actor(admin)):
        raise not_found(f"管理员 {login} ")
    return await list_admins()


class AuditEntry(BaseModel):
    id: int
    at: datetime
    actor: str
    entity: str
    action: str
    detail: dict[str, Any]


@router.get("/audit")
async def list_audit(
    entity: Annotated[
        str | None, Query(description="前缀，如 settings: 或 admin")
    ] = None,
    actor_filter: Annotated[str | None, Query(alias="actor")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AuditEntry]:
    """审计记录，新的在前"""
    conditions = []
    if entity:
        conditions.append(AuditLog.entity.startswith(entity))
    if actor_filter:
        conditions.append(AuditLog.actor == actor_filter)
    async with get_session() as session:
        total = await session.scalar(
            select(func.count()).select_from(AuditLog).where(*conditions)
        )
        rows = (
            await session.scalars(
                select(AuditLog)
                .where(*conditions)
                .order_by(AuditLog.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    return Page[AuditEntry](
        items=[
            AuditEntry(
                id=r.id,
                at=aware(r.at),
                actor=r.actor,
                entity=r.entity,
                action=r.action,
                detail=r.detail,
            )
            for r in rows
        ],
        total=total or 0,
    )
