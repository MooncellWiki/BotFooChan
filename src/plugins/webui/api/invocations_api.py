"""LLM 调用记录：列表、详情（对话回放）和统计"""

from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Query
from nonebot_plugin_orm import get_session
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from src.providers.llm.records import LLMInvocation, load_messages
from src.providers.llm.transcript import build_sections

from .common import Page, aware, not_found

router = APIRouter(prefix="/invocations", tags=["invocations"])

LOCAL_TZ = timezone(timedelta(hours=8))
"""按天统计时按北京时间分日"""


class InvocationSummary(BaseModel):
    id: int
    created_at: datetime
    task: str
    adapter: str | None
    session_id: str | None
    user_id: str | None
    model_alias: str | None
    provider: str | None
    model_name: str
    api_type: str
    status: str
    error: str | None
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    requests: int
    tool_calls: int
    web_search: bool
    output_preview: str
    has_messages: bool


class Section(BaseModel):
    kind: str
    """user / thinking / answer / tool / note"""
    data: dict[str, Any]


class InvocationDetail(InvocationSummary):
    bot_id: str | None
    sections: list[Section]
    sections_error: str = ""


def _summary(row: LLMInvocation) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": aware(row.created_at),
        "task": row.task,
        "adapter": row.adapter,
        "session_id": row.session_id,
        "user_id": row.user_id,
        "model_alias": row.model_alias,
        "provider": row.provider,
        "model_name": row.model_name,
        "api_type": row.api_type,
        "status": row.status,
        "error": row.error,
        "latency_ms": row.latency_ms,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "cache_read_tokens": row.cache_read_tokens,
        "requests": row.requests,
        "tool_calls": row.tool_calls,
        "web_search": row.web_search,
        "output_preview": row.output_preview,
        "has_messages": row.messages is not None,
    }


@router.get("")
async def list_invocations(
    task: str | None = None,
    status: str | None = None,
    model: Annotated[str | None, Query(description="模型别名或模型名")] = None,
    session: Annotated[str | None, Query(description="会话 id 里包含的字符串")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[InvocationSummary]:
    """调用记录，新的在前"""
    conditions = []
    if task:
        conditions.append(LLMInvocation.task == task)
    if status:
        conditions.append(LLMInvocation.status == status)
    if model:
        conditions.append(
            (LLMInvocation.model_alias == model) | (LLMInvocation.model_name == model)
        )
    if session:
        conditions.append(LLMInvocation.session_id.contains(session))
    async with get_session() as db:
        total = await db.scalar(
            select(func.count()).select_from(LLMInvocation).where(*conditions)
        )
        rows = (
            await db.scalars(
                select(LLMInvocation)
                .where(*conditions)
                .order_by(LLMInvocation.id.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    return Page[InvocationSummary](
        items=[InvocationSummary(**_summary(r)) for r in rows], total=total or 0
    )


class InvocationFilters(BaseModel):
    tasks: list[str]
    models: list[str]


@router.get("/filters")
async def get_invocation_filters() -> InvocationFilters:
    """筛选下拉框的候选值"""
    async with get_session() as db:
        tasks = (await db.scalars(select(LLMInvocation.task).distinct())).all()
        aliases = (await db.scalars(select(LLMInvocation.model_alias).distinct())).all()
    return InvocationFilters(
        tasks=sorted(tasks), models=sorted(a for a in aliases if a)
    )


class DailyStat(BaseModel):
    # 有默认值的字段在响应里也总会给，生成的前端类型别标成可选
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    date: str
    ok: int = 0
    error: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class GroupStat(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    key: str
    count: int = 0
    errors: int = 0
    tokens: int = 0
    avg_latency_ms: int = 0


class InvocationStats(BaseModel):
    days: list[DailyStat]
    by_task: list[GroupStat]
    by_model: list[GroupStat]
    last_24h: GroupStat


@router.get("/stats")
async def get_invocation_stats(
    days: Annotated[int, Query(ge=1, le=90)] = 14,
) -> InvocationStats:
    """最近几天的调用量、token 和错误"""
    now = datetime.now(UTC)
    since = now - timedelta(days=days)
    async with get_session() as db:
        rows = (
            await db.execute(
                select(
                    LLMInvocation.created_at,
                    LLMInvocation.task,
                    LLMInvocation.model_alias,
                    LLMInvocation.model_name,
                    LLMInvocation.status,
                    LLMInvocation.input_tokens,
                    LLMInvocation.output_tokens,
                    LLMInvocation.latency_ms,
                ).where(LLMInvocation.created_at >= since)
            )
        ).all()

    today = now.astimezone(LOCAL_TZ).date()
    daily = {
        (today - timedelta(days=i)).isoformat(): DailyStat(
            date=(today - timedelta(days=i)).isoformat()
        )
        for i in reversed(range(days))
    }
    groups: dict[str, dict[str, GroupStat]] = {"task": {}, "model": {}}
    latency: dict[tuple[str, str], int] = defaultdict(int)
    last_24h = GroupStat(key="24h")
    latency_24h = 0
    for at, task, alias, name, status, tin, tout, ms in rows:
        at = aware(at)
        failed = status != "ok"
        tokens = tin + tout
        if (day := daily.get(at.astimezone(LOCAL_TZ).date().isoformat())) is not None:
            if failed:
                day.error += 1
            else:
                day.ok += 1
            day.input_tokens += tin
            day.output_tokens += tout
        for kind, key in (("task", task), ("model", alias or name)):
            stat = groups[kind].setdefault(key, GroupStat(key=key))
            stat.count += 1
            stat.errors += failed
            stat.tokens += tokens
            latency[(kind, key)] += ms
        if at >= now - timedelta(hours=24):
            last_24h.count += 1
            last_24h.errors += failed
            last_24h.tokens += tokens
            latency_24h += ms

    for kind, stats in groups.items():
        for key, stat in stats.items():
            stat.avg_latency_ms = latency[(kind, key)] // max(stat.count, 1)
    last_24h.avg_latency_ms = latency_24h // max(last_24h.count, 1)
    return InvocationStats(
        days=list(daily.values()),
        by_task=sorted(groups["task"].values(), key=lambda s: -s.count),
        by_model=sorted(groups["model"].values(), key=lambda s: -s.count),
        last_24h=last_24h,
    )


@router.get("/{invocation_id}")
async def get_invocation(invocation_id: int) -> InvocationDetail:
    """一次调用的详情和对话回放"""
    async with get_session() as db:
        row = await db.get(LLMInvocation, invocation_id)
    if row is None:
        raise not_found(f"调用记录 {invocation_id} ")
    sections: list[Section] = []
    error = ""
    if row.messages:
        try:
            for section in build_sections(
                load_messages(row.messages), with_thinking=True
            ):
                sections.append(Section(kind=section.kind, data=asdict(section)))
        except Exception as e:
            error = f"对话内容解析失败：{e!r}"[:500]
    return InvocationDetail(
        **_summary(row), bot_id=row.bot_id, sections=sections, sections_error=error
    )
