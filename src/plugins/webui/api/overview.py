"""概览：版本、运行状态、在线的 bot，以及依赖的组件是否正常"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import cache
from importlib.metadata import version
from pathlib import Path
import platform
import tomllib
from typing import Literal

from fastapi import APIRouter
import nonebot
from nonebot import get_driver
from nonebot_plugin_orm import get_session
from nonebot_plugin_status.data_source import (
    get_bot_connect_time,
    get_cpu_status,
    get_memory_status,
    get_nonebot_run_time,
)
import psutil
from pydantic import BaseModel
from sqlalchemy import text

from src.plugins.webui.auth import CurrentAdmin
from src.providers.playwright import get_browser, is_connected
from src.providers.playwright import plugin_config as browser_config

router = APIRouter(tags=["overview"])

CHECK_TIMEOUT = 5
"""单项组件检查最多等几秒"""

_process = psutil.Process()


class Me(BaseModel):
    login: str
    name: str
    avatar_url: str
    environment: str


@router.get("/me")
async def get_me(admin: CurrentAdmin) -> Me:
    """当前登录的管理员"""
    return Me(**admin.model_dump(), environment=get_driver().env)


class BotInfo(BaseModel):
    self_id: str
    adapter: str
    connected_at: datetime | None


class Component(BaseModel):
    name: str
    status: Literal["ok", "error", "off"]
    detail: str = ""


class Overview(BaseModel):
    version: str
    environment: str
    python_version: str
    nonebot_version: str
    started_at: datetime | None
    """NoneBot 启动的时间"""
    cpu_percent: float
    """整机 CPU 占用（%）"""
    memory_percent: float
    """整机内存占用（%），容器里看到的是宿主机的"""
    process_memory: int
    """本进程占用的内存（RSS，字节）"""
    adapters: list[str]
    plugin_count: int
    bots: list[BotInfo]
    components: list[Component]


@cache
def _version() -> str:
    # 镜像里有 Dockerfile 写的 VERSION（tag 或 commit），本地开发时读 pyproject
    if (file := Path("VERSION")).is_file():
        return file.read_text("utf-8").strip()
    try:
        pyproject = tomllib.loads(Path("pyproject.toml").read_text("utf-8"))
        return pyproject["project"]["version"]
    except OSError, KeyError, tomllib.TOMLDecodeError:
        return "unknown"


async def _check_database() -> Component:
    async with get_session() as session:
        await session.execute(text("SELECT 1"))
    return Component(name="数据库", status="ok")


async def _check_browser() -> Component:
    if not browser_config.browser_ws_endpoint:
        # 本地模式下 get_browser() 会顺手把浏览器拉起来，这里只看不动
        if is_connected():
            return Component(name="浏览器", status="ok", detail="本地 Firefox")
        return Component(name="浏览器", status="off", detail="本地 Firefox，还没用到")
    if not (await get_browser()).is_connected():
        raise RuntimeError("连不上远程 Playwright")
    return Component(name="浏览器", status="ok", detail="远程 Playwright")


async def _run_check(name: str, check: Callable[[], Awaitable[Component]]) -> Component:
    try:
        async with asyncio.timeout(CHECK_TIMEOUT):
            return await check()
    except TimeoutError:
        return Component(name=name, status="error", detail=f"{CHECK_TIMEOUT} 秒没响应")
    except Exception as e:
        return Component(name=name, status="error", detail=str(e) or repr(e))


@router.get("/overview")
async def get_overview() -> Overview:
    """运行状态概览"""
    try:
        started_at = get_nonebot_run_time()
    except RuntimeError:
        started_at = None
    connect_times = get_bot_connect_time()
    cpu_percent, *components = await asyncio.gather(
        get_cpu_status(),
        _run_check("数据库", _check_database),
        _run_check("浏览器", _check_browser),
    )
    return Overview(
        version=_version(),
        environment=get_driver().env,
        python_version=platform.python_version(),
        nonebot_version=version("nonebot2"),
        started_at=started_at,
        cpu_percent=cpu_percent,
        memory_percent=get_memory_status().percent,
        process_memory=_process.memory_info().rss,
        adapters=sorted(nonebot.get_adapters()),
        plugin_count=len(nonebot.get_loaded_plugins()),
        bots=[
            BotInfo(
                self_id=bot_id,
                adapter=bot.adapter.get_name(),
                connected_at=connect_times.get(bot_id),
            )
            for bot_id, bot in nonebot.get_bots().items()
        ],
        components=components,
    )
