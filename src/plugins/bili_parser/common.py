from io import BytesIO
from typing import Any

import httpx
from nonebot.params import Depends
from nonebot.typing import T_State
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
    Alconna("bvideo", Args["type", ["av", "BV"]], Args["code", str]),
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


async def get_bili_cover(data: dict[str, Any] = BiliData()) -> BytesIO | None:
    async with httpx.AsyncClient(timeout=10) as client:
        if not data.get("data", {}).get("picture", ""):
            return

        r = await client.get(data["data"]["picture"])

        return BytesIO(r.content)


async def get_bili_data(
    state: T_State,
    type_: Match[str] = AlconnaMatch("type"),
    code: Match[str] = AlconnaMatch("code"),
):
    if data := await get_av_data(
        code.result,
        type_.result == "BV",
    ):
        state[BILI_DATA] = data
    else:
        await bili_parse.finish()


@bili_parse.handle(parameterless=[Depends(get_bili_data)])
async def _(
    data: dict[str, Any] = BiliData(),
    picture: BytesIO | None = Depends(get_bili_cover),
):
    bili_cover = (
        Image(url=data["data"]["picture"], raw=picture) if picture else Text("\n")
    )
    message = UniMessage([
        Text(f"{data['data']['title']}\n"),
        bili_cover,
        Text(
            f"小程序：m.q.qq.com/a/p/{data['data']['program_id']}?s={data['data']['program_path']}\n"
        ),
        Text(f"网页：{data['data']['link']}"),
    ])

    await bili_parse.send(message)
