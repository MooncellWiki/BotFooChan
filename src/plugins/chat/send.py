"""把回答发出去：闲聊的一两句话直接发，长回答连同思维链、联网来源、翻过的聊天
记录一起排版。

模型自己决定回多长（人设里交代了：闲聊短、认真提问给完整回答），这里只看
写出来的东西像不像「长回答」——够长、带 Markdown 结构，或者联网搜过（搜过就得
把出处摆出来）。长回答渲染成 DeepSeek 网页版样式的图片，渲染失败或关掉了图片
渲染时发纯文本。
"""

import re

from nonebot import logger
from nonebot_plugin_alconna.uniseg import Receipt, UniMessage

from src.providers.llm.chat import render_chat
from src.providers.llm.transcript import (
    Section,
    ToolSection,
    UserSection,
    render_transcript,
)

from .config import chat_config

RICH_LENGTH = 200
"""超过这么多字就按长回答排版"""

_MARKDOWN = re.compile(r"^\s*(#{1,6} |[-*+] |\d+[.)] |```|\|.*\|)", re.MULTILINE)
"""标题、列表、代码块、表格：纯文本里显示出来全是符号"""


def is_rich(answer: str, sections: list[Section]) -> bool:
    return (
        len(answer) > RICH_LENGTH
        or _MARKDOWN.search(answer) is not None
        or any(isinstance(s, ToolSection) and s.sources for s in sections)
    )


async def send_answer(message_id: str, answer: str, sections: list[Section]) -> Receipt:
    """发出回答，返回回执"""
    if not is_rich(answer, sections):
        return await UniMessage.text(answer).send(reply_to=message_id)

    if chat_config.render_image:
        try:
            image = await render_chat(sections, fallback=answer)
        except Exception as e:
            logger.opt(exception=e).warning("长回答渲染图片失败，改发纯文本")
        else:
            return await UniMessage.image(raw=image.data).send(reply_to=message_id)

    # 纯文本是回复着提问发的，提问本身就不再重复一遍
    text_sections = [s for s in sections if not isinstance(s, UserSection)]
    return await UniMessage.text(
        render_transcript(text_sections, flavor="text", fallback=answer)
    ).send(reply_to=message_id)
