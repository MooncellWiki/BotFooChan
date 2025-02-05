from io import BytesIO

import httpx
from nonebot import logger
from nonebot.adapters import Bot
from nonebot.params import Depends
from nonebot.typing import T_State
from nonebot_plugin_alconna import (
    Alconna,
    AlconnaMatch,
    Args,
    Image,
    Match,
    Text,
    UniMessage,
    on_alconna,
)
from nonebot_plugin_shorturl import ShortURL

from .consts import AV_REGEX, BILI_DATA, BV_REGEX
from .data_source import get_av_data
from .models import ShareClickResponseData

bili_parse = on_alconna(
    Alconna("bvideo", Args["code?", str]),
    use_cmd_start=True,
)
bili_parse.shortcut(AV_REGEX, {"args": ["{0}"]})
bili_parse.shortcut(BV_REGEX, {"args": ["{0}"]})


def _bili_data(state: T_State) -> ShareClickResponseData:
    return state[BILI_DATA]


def BiliData() -> ShareClickResponseData:
    return Depends(_bili_data, use_cache=False)


async def get_bili_cover(data: ShareClickResponseData = BiliData()):
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(data.picture)

            return BytesIO(r.content)

        except httpx.HTTPError as e:
            logger.opt(colors=True, exception=e).error(
                "Failed to fetch video cover from bilibili api"
            )


async def get_bili_data(
    state: T_State,
    code: Match[str] = AlconnaMatch("code"),
):
    if code.available:
        try:
            data = await get_av_data(code.result, code.result.startswith("BV"))

        except httpx.HTTPError as e:
            logger.opt(colors=True, exception=e).error(
                "Failed to fetch video metadata from bilibili api"
            )
            await bili_parse.finish(f"请求 Bilibili API 时发生错误：{e!r}")

        if data:
            state[BILI_DATA] = data.data
        else:
            await bili_parse.finish("未找到相关的视频信息")
    else:
        await bili_parse.finish("请输入正确的视频类型及视频号，例如：/bvideo av 1024")


@bili_parse.handle(parameterless=[Depends(get_bili_data)])
async def _(
    bot: Bot,
    data: ShareClickResponseData = BiliData(),
    cover_bytes: BytesIO | None = Depends(get_bili_cover),
):
    cover_url = data.picture
    mini_program_url = f"m.q.qq.com/a/p/{data.program_id}?s={data.program_path}"
    webpage_link = data.link

    if bot.adapter.get_name() == "QQ":
        mini_program_url = await ShortURL(url=mini_program_url).to_url()
        webpage_link = await ShortURL(url=webpage_link).to_url()

    bili_cover = Image(url=cover_url, raw=cover_bytes)
    message = UniMessage(
        [
            Text(f"{data.title}\n"),
            bili_cover,
            Text(f"小程序：{mini_program_url}\n"),
            Text(f"网页：{webpage_link}"),
        ]
    )

    try:
        await bili_parse.send(message)

    except Exception as e:
        logger.opt(colors=True, exception=e).error("Failed to send message")
        await bili_parse.send(f"发送消息时出现错误：{e!r}")
