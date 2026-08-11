"""群聊消息环形缓冲。

被 @ 时光看那一句话经常不知所云——「这个怎么搞」指的是上面哪条得看上下文。
这里用一个全局的 ``on_message`` 钩子把每个会话最近的消息记在内存里，
被 @ 时一并拼进提示词。

只放内存、不落库：需要的本来就只有最近几十条，重启后重新积累即可，
也免得把整个群的聊天记录长期存下来。
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from nonebot.adapters import Event
from nonebot_plugin_alconna.uniseg import At, AtAll, Emoji, Image, Text, UniMessage

TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class Record:
    """一条被记下来的消息"""

    user_id: str
    name: str
    text: str
    at: datetime
    message_id: str
    is_self: bool = False
    """是不是机器人自己说的"""


def scope_id(event: Event) -> str:
    """消息归属的会话（群/频道/私聊），与 what2eat 的取法保持一致"""
    user_id = event.get_user_id()
    try:
        session_id = event.get_session_id()
    except ValueError:
        return user_id
    # 各适配器的群/频道会话 id 都以 _{user_id} 结尾，去掉后就是会话本身
    return session_id.removesuffix(f"_{user_id}") or user_id


def sender_name(event: Event) -> str:
    """发送者的展示名。

    各适配器把昵称放在不同地方（OneBot 在 ``sender.card/nickname``、
    QQ 官方在 ``author.username``），没有统一接口，只能按已知的字段挨个试。
    """
    for owner in (getattr(event, "sender", None), getattr(event, "author", None)):
        if owner is None:
            continue
        for attr in ("card", "nickname", "username", "name"):
            if value := getattr(owner, attr, None):
                return str(value)
    return event.get_user_id()


def render_text(msg: UniMessage) -> str:
    """把消息渲染成一行纯文本，非文本段落用占位符表示"""
    chunks: list[str] = []
    for seg in msg:
        if isinstance(seg, Text):
            chunks.append(seg.text)
        elif isinstance(seg, At):
            chunks.append(f"@{seg.display or seg.target}")
        elif isinstance(seg, AtAll):
            chunks.append("@全体成员")
        elif isinstance(seg, Emoji):
            chunks.append(seg.name or "[表情]")
        elif isinstance(seg, Image):
            chunks.append("[图片]")
        else:
            chunks.append(f"[{seg.__class__.__name__.lower()}]")
    return " ".join("".join(chunks).split())


class Recorder:
    """按会话保留最近若干条消息"""

    def __init__(self, size: int) -> None:
        self.size = size
        self._buffers: dict[str, deque[Record]] = {}

    def _buffer(self, scope: str) -> deque[Record]:
        return self._buffers.setdefault(scope, deque(maxlen=self.size))

    def push(self, scope: str, record: Record) -> None:
        if record.text:
            self._buffer(scope).append(record)

    def record_event(self, event: Event, msg: UniMessage, message_id: str) -> None:
        self.push(
            scope_id(event),
            Record(
                user_id=event.get_user_id(),
                name=sender_name(event),
                text=render_text(msg),
                at=datetime.now(TZ),
                message_id=message_id,
            ),
        )

    def record_self(
        self, scope: str, name: str, text: str, self_id: str, message_id: str = ""
    ) -> None:
        """记下机器人自己的发言，下一轮对话才接得上自己说过的话"""
        self.push(
            scope,
            Record(
                user_id=self_id,
                name=name,
                text=" ".join(text.split()),
                at=datetime.now(TZ),
                message_id=message_id,
                is_self=True,
            ),
        )

    def recent(self, scope: str, limit: int) -> list[Record]:
        """最近的消息，旧的在前"""
        buffer = self._buffers.get(scope)
        if not buffer:
            return []
        return list(buffer)[-limit:]

    def find(self, scope: str, message_id: str) -> Record | None:
        """按消息 id 找回被回复的那条"""
        if not message_id:
            return None
        buffer = self._buffers.get(scope)
        if not buffer:
            return None
        return next((r for r in buffer if r.message_id == message_id), None)
