from typing import Any

import httpx
from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from nonebot.params import CommandArg, ArgPlainText

from . import nbnhhsh_config

nbnhhsh = on_command("hhsh", aliases={"nbnhhsh", "好好说话", "人话"}, priority=10)


@nbnhhsh.handle()
async def set_text(matcher: Matcher, args: Message = CommandArg()) -> None:
    if args.extract_plain_text():
        matcher.set_arg("text", args)


@nbnhhsh.got("text", prompt="请重新输入缩写")
async def got_text(text: str = ArgPlainText()):
    result = await guess(text)

    msg_seq = [
        f"原文：{r['name']}\n"
        f"翻译：{','.join(r.get('trans', []) or r.get('inputting',[])) or '暂无翻译'}"
        for r in result
    ]
    await nbnhhsh.finish("\n".join(msg_seq))


async def guess(text: str) -> Any:
    headers = {
        "user-agent": (
            "Mozilla/5.0 (Linux; Android 10; MIX 3) AppleWebKit/537.36 (KHTML, like"
            " Gecko) Chrome/86.0.4240.99 Mobile Safari/537.36"
        ),
        "referer": "https://lab.magiconch.com/nbnhhsh/",
    }

    json = {"text": text}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{nbnhhsh_config.nbnhhsh_api_endpoint}/api/nbnhhsh/guess",
            headers=headers,
            json=json,
        )
        resp = r.json()

        return resp
