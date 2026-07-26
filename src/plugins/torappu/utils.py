from typing import TYPE_CHECKING, Any, TypeVar

import httpx
from nonebot import logger
from nonebot.matcher import Matcher

from .data_source import list_versions

if TYPE_CHECKING:
    from collections.abc import Coroutine

T = TypeVar("T")


def find_version(versions: list[dict[str, Any]], key: str) -> int | None:
    """按版本 ID 或 res 版本号查找，返回列表下标"""
    for index, version in enumerate(versions):
        if key in (str(version["id"]), version["resVersion"]):
            return index
    return None


def format_size(size: float) -> str:
    for unit in ("B", "KiB", "MiB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"


async def call_api(matcher: type[Matcher], coro: "Coroutine[Any, Any, T]") -> T:
    try:
        return await coro
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await matcher.finish("未找到相关内容")
        logger.opt(colors=True, exception=e).error("请求 torappu 接口出错")
        await matcher.finish(
            f"请求接口失败（HTTP {e.response.status_code}）：\n{e.response.text[:200]}"
        )
    except httpx.HTTPError as e:
        logger.opt(colors=True, exception=e).error("请求 torappu 接口出错")
        await matcher.finish(f"请求接口出错，请稍后重试：\n{e!r}")


async def resolve_version(
    matcher: type[Matcher], key: str | None = None
) -> dict[str, Any]:
    """按版本 ID 或 res 版本号解析版本，缺省时返回最新版本"""
    versions = await call_api(matcher, list_versions())
    if not versions:
        await matcher.finish("版本列表为空")
    if key is None:
        return versions[-1]
    index = find_version(versions, key)
    if index is None:
        await matcher.finish(f"未找到版本：{key}")
    return versions[index]
