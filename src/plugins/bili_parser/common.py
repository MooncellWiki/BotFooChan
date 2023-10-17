from io import BytesIO
from typing import Any, Annotated

import httpx
from nonebot import on_regex
from nonebot.typing import T_State
from nonebot.params import Depends, RegexGroup
from nonebot_plugin_saa import Text, Image, MessageFactory

from .data_source import get_av_data

biliav = on_regex(r"av(\d{1,12})|BV(1[A-Za-z0-9]{2}4.1.7[A-Za-z0-9]{2})")

BILI_DATA = "_bili_data"


def _bili_data(state: T_State) -> dict[str, Any]:
    return state[BILI_DATA]


def BiliData() -> dict[str, Any]:
    return Depends(_bili_data, use_cache=False)


async def get_bili_cover(data: Annotated[dict[str, Any], BiliData()]) -> BytesIO | None:
    async with httpx.AsyncClient(timeout=10) as client:
        if not data.get("data", {}).get("picture", ""):
            return

        r = await client.get(data["data"]["picture"])

        return BytesIO(r.content)


async def get_bili_data(
    state: T_State, code: Annotated[tuple[str | Any, ...], RegexGroup()]
):
    avcode, bvcode = code

    if data := await get_av_data(
        avcode or bvcode,
        bool(bvcode),
    ):
        state[BILI_DATA] = data
    else:
        await biliav.finish()


@biliav.handle(parameterless=[Depends(get_bili_data)])
async def _(
    data: Annotated[dict[str, Any], BiliData()],
    picture: Annotated[BytesIO | None, Depends(get_bili_cover)],
):
    msg = MessageFactory(
        [
            Text(f"{data['data']['title']}\n"),
            Image(picture) if picture else Text("\n"),
            Text(
                f"小程序：m.q.qq.com/a/p/{data['data']['program_id']}?s={data['data']['program_path']}\n"
            ),
            Text(f"网页：{data['data']['link']}"),
        ]
    )

    await msg.send()
