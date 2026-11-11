"""Discord 单条消息最多 2000 字，超了整条发不出去（400 Invalid Form Body）。

长回答、长动态在别的平台都能一条发完，没必要每个插件各自去拆：在调用
``create_message`` 之前统一切开。前面几段只带文字（第一段带上引用，看得出是在
回复谁），附件、embed 等跟着最后一段，返回的也是最后一段，后续按它记 id。
"""

from typing import Any

from nonebot.adapters import Bot
from nonebot.adapters.discord import Bot as DiscordBot

DISCORD_MAX_LENGTH = 2000
CHUNK_LENGTH = 1900
"""留点余量：Discord 计字的口径和 Python 的 len 不完全一致"""


def split_text(text: str, limit: int = CHUNK_LENGTH) -> list[str]:
    """按行切成不超过 ``limit`` 字的几段，单行太长再硬切"""
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = ""
        current += line
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk.strip()] or [text[:limit]]


@Bot.on_calling_api
async def _split_long_message(bot: Bot, api: str, data: dict[str, Any]) -> None:
    if not isinstance(bot, DiscordBot) or api != "create_message":
        return
    content = data.get("content")
    if not isinstance(content, str) or len(content) <= DISCORD_MAX_LENGTH:
        return

    *heads, last = split_text(content)
    reference = data.pop("message_reference", None) if heads else None
    for index, chunk in enumerate(heads):
        extra: dict[str, Any] = {}
        if index == 0 and reference is not None:
            extra["message_reference"] = reference
        if (mentions := data.get("allowed_mentions")) is not None:
            extra["allowed_mentions"] = mentions
        await bot.create_message(channel_id=data["channel_id"], content=chunk, **extra)
    data["content"] = last
