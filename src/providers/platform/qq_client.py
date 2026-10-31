"""QQ 客户端协议（OneBot V11、Milky）下的消息构造与发送。

两种协议端面向的都是 QQ 号/群号（:class:`QQUserInfo` / :class:`QQGroupInfo`），
只是消息段和接口各是一套。插件需要直接给 QQ 客户端拼消息时走这里，不用每处分开写。
"""

from typing import Any

from nonebot.adapters import Bot, MessageSegment
from nonebot.adapters.milky import Bot as MilkyBot
from nonebot.adapters.milky import MessageSegment as MilkyMS
from nonebot.adapters.onebot.v11 import Bot as OneBotBot
from nonebot.adapters.onebot.v11 import Message as OneBotMessage
from nonebot.adapters.onebot.v11 import MessageSegment as OneBotMS

from .targets import QQGroupInfo, QQUserInfo


def is_qq_client(bot: Bot) -> bool:
    return isinstance(bot, MilkyBot | OneBotBot)


def _milky_image(image: bytes | str) -> MilkyMS:
    return (
        MilkyMS.image(raw=image) if isinstance(image, bytes) else MilkyMS.image(image)
    )


def image_segment(bot: Bot, image: bytes | str) -> MessageSegment:
    """图片段，``image`` 为图片数据或 URL"""
    if isinstance(bot, MilkyBot):
        return _milky_image(image)
    if isinstance(bot, OneBotBot):
        return OneBotMS.image(image)
    raise TypeError(f"Not a QQ client bot: {bot!r}")


async def _send_milky(
    bot: MilkyBot, target: QQUserInfo | QQGroupInfo, segment: MilkyMS
) -> Any:
    if isinstance(target, QQUserInfo):
        return await bot.send_private_message(
            user_id=target.qq_user_id, message=segment
        )
    return await bot.send_group_message(group_id=target.qq_group_id, message=segment)


async def _send_onebot(
    bot: OneBotBot, target: QQUserInfo | QQGroupInfo, segment: OneBotMS
) -> Any:
    if isinstance(target, QQUserInfo):
        return await bot.send_private_msg(
            user_id=target.qq_user_id, message=OneBotMessage(segment)
        )
    return await bot.send_group_msg(
        group_id=target.qq_group_id, message=OneBotMessage(segment)
    )


async def send_text(bot: Bot, target: QQUserInfo | QQGroupInfo, text: str) -> Any:
    """主动发纯文本，返回协议端的原始结果（交给 ``extract_sent_message``）。

    OneBot 的字符串消息会按 CQ 码解析，这里包成文本段，内容里的 CQ 码不会生效。
    """
    if isinstance(bot, MilkyBot):
        return await _send_milky(bot, target, MilkyMS.text(text))
    if isinstance(bot, OneBotBot):
        return await _send_onebot(bot, target, OneBotMS.text(text))
    raise TypeError(f"Not a QQ client bot: {bot!r}")


async def send_image(
    bot: Bot, target: QQUserInfo | QQGroupInfo, image: bytes | str
) -> Any:
    """主动发图片（数据或 URL），返回协议端的原始结果"""
    if isinstance(bot, MilkyBot):
        return await _send_milky(bot, target, _milky_image(image))
    if isinstance(bot, OneBotBot):
        return await _send_onebot(bot, target, OneBotMS.image(image))
    raise TypeError(f"Not a QQ client bot: {bot!r}")
