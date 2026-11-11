"""运维：日志、插件、定时任务、Torappu 重跑"""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
import httpx
import nonebot
from pydantic import BaseModel, Field

from src.plugins.webui import logs
from src.plugins.webui.auth import CurrentAdmin
from src.providers.settings import audit

from .common import actor, bad_request, not_found, unavailable

router = APIRouter(tags=["ops"])


# ---------- 日志 ----------

LEVELS = {"INFO": 20, "SUCCESS": 25, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


class LogLine(BaseModel):
    id: int
    time: datetime
    level: str
    name: str
    message: str


class LogBatch(BaseModel):
    items: list[LogLine]
    last_id: int
    """下次带着它来拉增量"""


@router.get("/logs")
async def get_logs(
    after: Annotated[int, Query(ge=0)] = 0,
    level: Literal["INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"] = "INFO",
    q: Annotated[str | None, Query(description="只看包含这段文字的")] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> LogBatch:
    """最近的日志（内存里最多留 2000 条，重启清空），按 id 增量拉"""
    entries = logs.entries(after)
    last_id = entries[-1].id if entries else after
    minimum = LEVELS[level]
    matched = [
        e
        for e in entries
        if e.level_no >= minimum
        and (not q or q.lower() in e.message.lower() or q.lower() in e.name.lower())
    ][-limit:]
    return LogBatch(
        items=[
            LogLine(id=e.id, time=e.time, level=e.level, name=e.name, message=e.message)
            for e in matched
        ],
        last_id=last_id,
    )


# ---------- 插件 ----------


class MatcherInfo(BaseModel):
    type: str
    priority: int
    block: bool
    rules: list[str]
    """规则里各个检查函数的名字"""


class PluginInfo(BaseModel):
    id: str
    name: str
    description: str
    usage: str
    type: str | None
    homepage: str | None
    module: str
    parent: str | None
    matchers: list[MatcherInfo]


def _callable_name(obj: Any) -> str:
    call = getattr(obj, "call", obj)
    return getattr(call, "__qualname__", None) or type(call).__name__


@router.get("/plugins")
async def list_plugins() -> list[PluginInfo]:
    """已加载的插件和它们的事件响应器"""
    out: list[PluginInfo] = []
    for plugin in sorted(nonebot.get_loaded_plugins(), key=lambda p: p.id_):
        meta = plugin.metadata
        out.append(
            PluginInfo(
                id=plugin.id_,
                name=meta.name if meta else plugin.name,
                description=meta.description if meta else "",
                usage=meta.usage if meta else "",
                type=meta.type if meta else None,
                homepage=meta.homepage if meta else None,
                module=plugin.module_name,
                parent=plugin.parent_plugin.id_ if plugin.parent_plugin else None,
                matchers=[
                    MatcherInfo(
                        type=m.type,
                        priority=m.priority,
                        block=m.block,
                        rules=[_callable_name(c) for c in m.rule.checkers],
                    )
                    for m in sorted(plugin.matcher, key=lambda m: m.priority)
                ],
            )
        )
    return out


# ---------- 定时任务 ----------


class JobInfo(BaseModel):
    id: str
    name: str
    func: str
    trigger: str
    next_run_time: datetime | None
    """None 表示暂停了（或调度器还没启动）"""
    pending: bool
    """调度器还没启动，任务还没排上"""


def _scheduler() -> Any:
    if nonebot.get_plugin("nonebot_plugin_apscheduler") is None:
        raise unavailable("定时任务插件没有加载")
    from nonebot_plugin_apscheduler import scheduler

    return scheduler


def _jobs() -> list[JobInfo]:
    return [
        JobInfo(
            id=job.id,
            name=job.name,
            func=str(getattr(job, "func_ref", job.func)),
            trigger=str(job.trigger),
            # 调度器启动前的任务还没有 next_run_time 这个属性
            next_run_time=getattr(job, "next_run_time", None),
            pending=getattr(job, "pending", False),
        )
        for job in sorted(
            _scheduler().get_jobs(), key=lambda j: str(getattr(j, "func_ref", j.id))
        )
    ]


@router.get("/scheduler/jobs")
async def list_jobs() -> list[JobInfo]:
    """定时任务"""
    return _jobs()


@router.post("/scheduler/jobs/{job_id}/{action}")
async def control_job(
    job_id: str, action: Literal["run", "pause", "resume"], admin: CurrentAdmin
) -> list[JobInfo]:
    """立即执行、暂停或恢复一个定时任务"""
    scheduler = _scheduler()
    job = scheduler.get_job(job_id)
    if job is None:
        raise not_found(f"定时任务 {job_id} ")
    if action == "run":
        job.modify(next_run_time=datetime.now(scheduler.timezone))
    elif action == "pause":
        job.pause()
    else:
        job.resume()
    await audit(actor(admin), "scheduler", action, {"job": job_id, "name": job.name})
    return _jobs()


# ---------- Torappu ----------


class TorappuVersion(BaseModel):
    id: int
    client_version: str
    res_version: str
    raw: dict[str, Any]


def _torappu() -> Any:
    if nonebot.get_plugin("torappu") is None:
        raise unavailable("torappu 插件没有加载")
    from src.plugins.torappu import data_source

    return data_source


@router.get("/torappu/versions")
async def list_torappu_versions(
    limit: Annotated[int, Query(ge=1, le=200)] = 30,
) -> list[TorappuVersion]:
    """最近的版本，新的在前"""
    versions = await _torappu().list_versions()
    return [
        TorappuVersion(
            id=int(v["id"]),
            client_version=str(v["clientVersion"]),
            res_version=str(v["resVersion"]),
            raw=v,
        )
        for v in reversed(versions[-limit:])
    ]


class RelaunchIn(BaseModel):
    version_id: int
    prev_version_id: int
    include: str | None = Field(default=None, max_length=500)
    exclude: str | None = Field(default=None, max_length=500)


class RelaunchResult(BaseModel):
    container_name: str
    status: str
    raw: dict[str, Any]


@router.post("/torappu/relaunch")
async def relaunch_torappu(body: RelaunchIn, admin: CurrentAdmin) -> RelaunchResult:
    """发起 torappu 重跑（等同 /重跑）"""
    from src.plugins.torappu.config import plugin_config

    source = _torappu()
    if not plugin_config.torappu_auth_token:
        raise unavailable("没配 torappu 的 token，发起不了重跑")
    versions = {int(v["id"]): v for v in await source.list_versions()}
    target = versions.get(body.version_id)
    prev = versions.get(body.prev_version_id)
    if target is None or prev is None:
        raise bad_request("选的版本不存在")
    try:
        result = await source.launch_container(
            target["clientVersion"],
            target["resVersion"],
            prev["clientVersion"],
            prev["resVersion"],
            body.include or None,
            body.exclude or None,
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"torappu 返回 {e.response.status_code}：{e.response.text[:500]}",
        ) from e
    except httpx.HTTPError as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"连不上 torappu：{e!r}"
        ) from e
    await audit(
        actor(admin),
        "torappu",
        "relaunch",
        {
            "from": prev["resVersion"],
            "to": target["resVersion"],
            "include": body.include,
            "exclude": body.exclude,
        },
    )
    return RelaunchResult(
        container_name=str(result.get("container_name", "")),
        status=str(result.get("status", "")),
        raw=result,
    )
