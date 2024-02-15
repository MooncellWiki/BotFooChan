from io import BytesIO
from typing import Any

import httpx
from nonebot import logger
from nonebot.adapters import Bot
from nonebot.params import Depends
from nonebot.typing import T_State
from nonebot_plugin_shorturl import ShortURL
from nonebot_plugin_alconna import (
    Args,
    Text,
    Image,
    Match,
    Alconna,
    UniMessage,
    AlconnaMatch,
    on_alconna,
)

from .data_source import get_av_data

bili_parse = on_alconna(
    Alconna("bvideo", Args["type?", ["av", "BV"]], Args["code?", str]),
    use_cmd_start=True,
)
bili_parse.shortcut(r".*av(\d{1,12}).*", {"args": ["av", "{0}"]})
bili_parse.shortcut(
    r".*BV(1[A-Za-z0-9]{2}4.1.7[A-Za-z0-9]{2}).*", {"args": ["BV", "{0}"]}
)

BILI_DATA = "_bili_data"


def _bili_data(state: T_State) -> dict[str, Any]:
    return state[BILI_DATA]


def BiliData() -> dict[str, Any]:
    return Depends(_bili_data, use_cache=False)


async def get_bili_cover(data: dict[str, Any] = BiliData()):
    async with httpx.AsyncClient(timeout=10) as client:
        if not data.get("data", {}).get("picture", ""):
            return None

        try:
            r = await client.get(data["data"]["picture"])
        except httpx.HTTPError as e:
            logger.opt(colors=True, exception=e).error(
                "Failed to fetch video cover from bilibili api"
            )
            return None

        return BytesIO(r.content)


async def get_bili_data(
    state: T_State,
    type_: Match[str] = AlconnaMatch("type"),
    code: Match[str] = AlconnaMatch("code"),
):
    if type_.available and code.available:
        is_bv = type_.result == "BV"

        try:
            data = await get_av_data(code.result, is_bv)
        except httpx.HTTPError as e:
            logger.opt(colors=True, exception=e).error(
                "Failed to fetch video metadata from bilibili api"
            )
            await bili_parse.finish(f"请求 Bilibili API 时发生错误：{e}")

        if data:
            state[BILI_DATA] = data

        else:
            await bili_parse.finish("未找到相关的视频信息")

    else:
        await bili_parse.finish("请输入正确的视频类型及视频号，例如：/bvideo av 1024")


@bili_parse.handle(parameterless=[Depends(get_bili_data)])
async def _(
    bot: Bot,
    data: dict[str, Any] = BiliData(),
    cover_bytes: BytesIO | None = Depends(get_bili_cover),
):
    cover_url = data["data"]["picture"]
    mini_program_url = (
        f"m.q.qq.com/a/p/{data['data']['program_id']}?s={data['data']['program_path']}"
    )
    webpage_link = data["data"]["link"]

    if bot.adapter.get_name() == "QQ":
        mini_program_url = await ShortURL(url=mini_program_url).to_url()
        webpage_link = await ShortURL(url=webpage_link).to_url()

    bili_cover = Image(url=cover_url, raw=cover_bytes)
    message = UniMessage(
        [
            Text(f"{data['data']['title']}\n"),
            bili_cover,
            Text(f"小程序：{mini_program_url}\n"),
            Text(f"网页：{webpage_link}"),
        ]
    )

    try:
        await bili_parse.send(message)

    except Exception as e:
        logger.opt(colors=True, exception=e).error("Failed to send message")
        await bili_parse.send(f"进行平台侧调用时出现错误：{e}")
