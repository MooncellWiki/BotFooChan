from typing import Any

import httpx
from nonebot import logger
from nonebot_plugin_alconna import Alconna, Args, Match, on_alconna

from . import __plugin_meta__, config

nbnhhsh = on_alconna(
    Alconna("hhsh", Args["text?", str]),
    aliases={"nbnhhsh", "好好说话", "人话"},
    priority=10,
    use_cmd_start=True,
)


def get_splitted_text(r):
    translates = r.get("trans")
    guesses = r.get("inputting")

    return config.nbnhhsh_split_char.join(translates or guesses or []) or "暂无翻译"


@nbnhhsh.handle()
async def set_text(text: Match[str]) -> None:
    if text.available:
        try:
            result = await guess(text.result)
        except httpx.HTTPError as e:
            logger.opt(colors=True, exception=e).error(
                "failed to fetch guess from nbnhhsh api"
            )
            await nbnhhsh.finish(f"查询出错，请稍后重试：\n{e!r}")

        if not result:
            await nbnhhsh.finish("未找到相关结果")

        msg_seq = [
            f"原文：{r.get('name')}\n翻译：{get_splitted_text(r)}" for r in result
        ]
        await nbnhhsh.finish("\n".join(msg_seq))

    else:
        await nbnhhsh.finish(__plugin_meta__.usage)


async def guess(text: str) -> list[dict[str, Any]]:
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
            httpx.URL(str(config.nbnhhsh_api_endpoint)).join("/api/nbnhhsh/guess"),
            headers=headers,
            json=json,
        )
        resp = r.json()

        return resp
