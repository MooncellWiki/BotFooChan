"""带过期时间的键值缓存 provider。

QQ-GitHub-Bot 原本把短命数据都放在 Redis 里：消息与 Issue/PR 的对应关系、OAuth
state、webhook 节流标记，以及渲染好的图片和 OpenGraph 图片。合进来以后只剩一个
进程，为这些专门跑一个 Redis 不划算，改成落在 localstore 的缓存目录里：

- 每个键一个文件，文件名是键的 sha256，按前两位分子目录
- 文件头 8 字节记过期时间戳（大端 double，不过期记 +inf），后面是原样的值
- 读到过期的顺手删掉，再由后台任务每小时整体清扫一遍

单进程部署（``MAX_WORKERS=1``）下没有并发写同一个键的问题；写入先落临时文件再
``os.replace``，中途重启也不会留下半截文件。
"""

import asyncio
import contextlib
from datetime import timedelta
from hashlib import sha256
import math
import os
from pathlib import Path
import struct
import time
from uuid import uuid4

from nonebot import get_driver, logger, require
from nonebot.utils import run_sync

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_cache_dir

_HEADER = struct.Struct(">d")
"""过期时间戳"""

SWEEP_INTERVAL = timedelta(hours=1)

_cache_dir = get_plugin_cache_dir()
_driver = get_driver()


def _path(key: str) -> Path:
    digest = sha256(key.encode()).hexdigest()
    return _cache_dir / digest[:2] / digest


def _read(path: Path) -> bytes | None:
    """读出未过期的值；不存在、已过期或文件残缺都当没有"""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None

    if len(raw) < _HEADER.size or _HEADER.unpack_from(raw)[0] <= time.time():
        path.unlink(missing_ok=True)
        return None
    return raw[_HEADER.size :]


@run_sync
def _get(key: str) -> bytes | None:
    return _read(_path(key))


@run_sync
def _set(key: str, value: bytes, expire_at: float) -> None:
    path = _path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid4().hex}")
    tmp.write_bytes(_HEADER.pack(expire_at) + value)
    os.replace(tmp, path)


@run_sync
def _delete(key: str) -> None:
    _path(key).unlink(missing_ok=True)


async def get(key: str) -> bytes | None:
    """读取缓存，不存在或已过期返回 ``None``"""
    return await _get(key)


async def set(key: str, value: bytes | str, ex: timedelta | None = None) -> None:
    """写入缓存，``ex`` 为空表示不过期"""
    if isinstance(value, str):
        value = value.encode()
    expire_at = math.inf if ex is None else time.time() + ex.total_seconds()
    await _set(key, value, expire_at)


async def exists(key: str) -> bool:
    return await get(key) is not None


async def delete(key: str) -> None:
    await _delete(key)


@run_sync
def sweep() -> None:
    """清掉所有过期的缓存文件，以及写到一半就中断留下的临时文件"""
    removed = 0
    now = time.time()
    for path in _cache_dir.glob("*/*"):
        try:
            if path.name.startswith("."):
                # 临时文件正常情况下转瞬即逝，放了一小时还在的就是中断遗留
                expired = path.stat().st_mtime < now - 3600
            else:
                with path.open("rb") as f:
                    header = f.read(_HEADER.size)
                expired = len(header) < _HEADER.size or _HEADER.unpack(header)[0] <= now
        except FileNotFoundError:  # 刚好被读取方删掉了
            continue
        if expired:
            path.unlink(missing_ok=True)
            removed += 1
    if removed:
        logger.debug(f"清理了 {removed} 个过期缓存")


# 不用 apscheduler：provider 先于 PLUGINS 加载，在这里 require 它会让后面按 PLUGINS
# 加载时报「Plugin already exists」
async def _sweep_forever() -> None:
    while True:
        try:
            await sweep()
        except Exception as e:
            logger.opt(exception=e).warning("清理过期缓存失败")
        await asyncio.sleep(SWEEP_INTERVAL.total_seconds())


_sweeper: asyncio.Task | None = None


@_driver.on_startup
async def _start_sweeper() -> None:
    global _sweeper
    _sweeper = asyncio.create_task(_sweep_forever())


@_driver.on_shutdown
async def _stop_sweeper() -> None:
    if _sweeper is not None:
        _sweeper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _sweeper
