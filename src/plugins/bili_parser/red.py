from io import BytesIO
from typing import Any, Annotated

import httpx
from nonebot import on_regex
from nonebot.params import RegexGroup
from nonebot.adapters.red import Message, MessageSegment

from .data_source import get_av_data

biliav = on_regex(r"av(\d{1,12})|BV(1[A-Za-z0-9]{2}4.1.7[A-Za-z0-9]{2})")


@biliav.handle()
async def _(code: Annotated[tuple[Any, ...], RegexGroup()]):
    if not (
        data := await get_av_data(
            code[0] or code[1],
            code[1] and True or False,
        )
    ):
        return

    async with httpx.AsyncClient(timeout=10) as client:
        if not data.get("data", {}).get("picture", ""):
            return

        r = await client.get(data["data"]["picture"])

    await biliav.send(
        Message(
            [
                MessageSegment.text(f"{data['data']['title']}\n"),
                MessageSegment.image(BytesIO(r.content)),
                MessageSegment.text(
                    f"小程序：m.q.qq.com/a/p/{data['data']['program_id']}?s={data['data']['program_path']}\n"
                ),
                MessageSegment.text(f"网页：{data['data']['link']}"),
            ]
        )
    )
