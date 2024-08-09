import httpx
from nonebot import logger
from nonebot_plugin_alconna import Args, Match, Alconna, on_alconna

from . import __plugin_meta__

server_status = on_alconna(
    Alconna("server_status", Args["type?", str]),
    aliases={"服务器状态"},
    priority=10,
    use_cmd_start=True,
)


async def fetch_status(type: str):
    match type:
        case "国服":
            ...
        case "日服":
            ...


@server_status.handle()
async def handle_default(type: Match[str]) -> None:
    if type.available:
        try:
            result = await fetch_status(type.result)
        except httpx.HTTPError as e:
            logger.opt(colors=True, exception=e).error(
                "failed to fetch guess from nbnhhsh api"
            )
            await server_status.finish(f"查询出错，请稍后重试：\n{e}")

        if not result:
            await server_status.finish("查询结果为空")

        await server_status.finish(result)

    else:
        await server_status.finish(__plugin_meta__.usage)
