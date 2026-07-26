import httpx
from nonebot import logger
from nonebot_plugin_alconna import Alconna, Args, Match, on_alconna

from .data_source import (
    MAINT_ACTION_CN,
    MAINT_ACTION_JP,
    fetch_gamedata_cn,
    fetch_gamedata_jp,
    format_server_time,
    get_action,
    get_detail,
    get_title,
)

server_status = on_alconna(
    Alconna("server_status", Args["type?", str]),
    aliases={"服务器状态"},
    priority=10,
    use_cmd_start=True,
)


async def fetch_status(type: str) -> str | None:
    match type:
        case "国服":
            data = await fetch_gamedata_cn()
            maint_action = MAINT_ACTION_CN
        case "日服":
            data = await fetch_gamedata_jp()
            maint_action = MAINT_ACTION_JP
        case _:
            return None

    ts = format_server_time(data)
    if get_action(data) != maint_action:
        return f"FGO{type}服务器状态：正常\n获取时间：{ts}"

    lines = [f"FGO{type}服务器状态：维护中"]
    if title := get_title(data):
        lines.append(f"维护标题：{title}")
    if detail := get_detail(data):
        lines.append(f"维护公告：\n{detail}")
    lines.append(f"获取时间：{ts}")
    return "\n".join(lines)


@server_status.handle()
async def handle_default(type: Match[str]) -> None:
    if not type.available:
        await server_status.finish("请输入正确的服务器类型，例如：/服务器状态 国服")

    try:
        result = await fetch_status(type.result)
    except httpx.HTTPError as e:
        logger.opt(colors=True, exception=e).error("请求服务器出错")
        await server_status.finish(f"查询出错，请稍后重试：\n{e}")

    if not result:
        await server_status.finish("请输入正确的服务器类型，例如：/服务器状态 国服")

    await server_status.finish(result)
