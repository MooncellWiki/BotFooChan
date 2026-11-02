"""OneBot v11 消息（CQ 码字符串、消息段数组）转成 QQ 官方机器人的消息。

只认外部推送用得到的 text 和图片、语音、视频，别的段直接报错。at 段例外，直接
去掉：官方机器人只认 member_openid，QQ 号换算不过去，推送里的 at 也不影响正文。
"""

from base64 import b64decode
import binascii
from collections.abc import Callable
from typing import Any

from nonebot.adapters.onebot.v11 import Message as OneBotMessage
from nonebot.adapters.onebot.v11 import MessageSegment as OneBotMS
from nonebot.adapters.qq import Message as QQMessage
from nonebot.adapters.qq import MessageSegment as QQMS

MEDIA_BY_URL: dict[str, Callable[[str], QQMS]] = {
    "image": QQMS.image,
    "record": QQMS.audio,
    "video": QQMS.video,
}
MEDIA_BY_DATA: dict[str, Callable[[bytes], QQMS]] = {
    "image": QQMS.file_image,
    "record": QQMS.file_audio,
    "video": QQMS.file_video,
}
QQ_MEDIA_TYPES = frozenset(
    {"image", "audio", "video", "file_image", "file_audio", "file_video"}
)


class UnsupportedMessage(ValueError):
    pass


def parse_onebot_message(message: Any, auto_escape: bool = False) -> OneBotMessage:
    """按 OneBot v11 的规则解析 ``message`` 参数"""
    if isinstance(message, str):
        return OneBotMessage(OneBotMS.text(message) if auto_escape else message)
    if isinstance(message, dict):
        message = [message]
    if isinstance(message, list):
        segments = []
        for seg in message:
            if not isinstance(seg, dict) or not isinstance(seg.get("type"), str):
                raise UnsupportedMessage(f"消息段格式不对：{seg!r}")
            segments.append(OneBotMS(seg["type"], seg.get("data") or {}))
        return OneBotMessage(segments)
    raise UnsupportedMessage(f"message 应为字符串、消息段或消息段数组：{message!r}")


def _media(seg: OneBotMS) -> QQMS:
    # http(s) 的文件由 QQ 服务器自己去拉，得是公网能访问的地址；
    # 调用方不在本机，本地文件路径传过来也读不到
    file = str(seg.data.get("url") or seg.data.get("file") or "")
    if file.startswith(("http://", "https://")):
        return MEDIA_BY_URL[seg.type](file)
    if file.startswith("base64://"):
        try:
            data = b64decode(file.removeprefix("base64://"))
        except binascii.Error as e:
            raise UnsupportedMessage(f"{seg.type} 段的 base64 不对：{e}") from e
        if not data:
            raise UnsupportedMessage(f"{seg.type} 段的 base64 是空的")
        return MEDIA_BY_DATA[seg.type](data)
    raise UnsupportedMessage(f"{seg.type} 段只支持 http(s):// 或 base64:// 的文件")


def _has_media(message: QQMessage) -> bool:
    return any(seg.type in QQ_MEDIA_TYPES for seg in message)


def to_qq(message: OneBotMessage) -> list[QQMessage]:
    """转成一条或几条官方机器人的消息。

    官方的富媒体消息一条只能带一个文件，有几个文件就拆成几条：每条带一个文件和它
    前面的文字，最后一个文件后面的文字跟着最后一条。只有一个文件时不拆。
    """
    chunks: list[QQMessage] = []
    current = QQMessage()
    for seg in message:
        match seg.type:
            case "text":
                if not (text := str(seg.data.get("text", ""))):
                    continue
                converted = QQMS.text(text)
            case "image" | "record" | "video":
                converted = _media(seg)
            case "at":
                continue
            case _:
                raise UnsupportedMessage(f"不支持 {seg.type} 消息段")
        if _has_media(current):
            chunks.append(current)
            current = QQMessage()
        current.append(converted)

    if chunks and not _has_media(current):
        chunks[-1].extend(current)
    elif current:
        chunks.append(current)
    if not chunks:
        raise UnsupportedMessage("消息为空")
    return chunks
