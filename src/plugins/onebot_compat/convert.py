"""OneBot v11 消息（CQ 码字符串、消息段数组）转成 Milky 消息。

只认外部推送用得到的几种段；别的段直接报错，不悄悄丢掉。
"""

from typing import Any

from nonebot.adapters.milky import Message as MilkyMessage
from nonebot.adapters.milky import MessageSegment as MilkyMS
from nonebot.adapters.onebot.v11 import Message as OneBotMessage
from nonebot.adapters.onebot.v11 import MessageSegment as OneBotMS

URI_SCHEMES = ("http://", "https://", "base64://")


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


def _media_uri(seg: OneBotMS) -> str:
    # 调用方和协议端不在一台机器上，本地文件路径传过去也读不到
    file = str(seg.data.get("url") or seg.data.get("file") or "")
    if not file.startswith(URI_SCHEMES):
        raise UnsupportedMessage(f"{seg.type} 段只支持 http(s):// 或 base64:// 的文件")
    return file


def to_milky(message: OneBotMessage) -> MilkyMessage:
    result = MilkyMessage()
    for seg in message:
        match seg.type:
            case "text":
                result.append(MilkyMS.text(str(seg.data.get("text", ""))))
            case "at":
                qq = str(seg.data.get("qq", ""))
                if qq == "all":
                    result.append(MilkyMS.mention_all())
                elif qq.isdigit():
                    result.append(MilkyMS.mention(int(qq)))
                else:
                    raise UnsupportedMessage(f"at 段的 qq 不对：{qq!r}")
            case "face":
                result.append(MilkyMS.face(str(seg.data.get("id", ""))))
            case "reply":
                result.append(MilkyMS.reply(int(seg.data["id"])))
            case "image":
                result.append(MilkyMS.image(_media_uri(seg)))
            case "record":
                result.append(MilkyMS.record(_media_uri(seg)))
            case "video":
                result.append(MilkyMS.video(_media_uri(seg)))
            case _:
                raise UnsupportedMessage(f"不支持 {seg.type} 消息段")
    if not result:
        raise UnsupportedMessage("消息为空")
    return result
