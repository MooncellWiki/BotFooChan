"""群聊消息环形缓冲。

只放内存、不落库：需要的本来就只有最近一两百条，重启后重新积累即可，
也免得把整个群的聊天记录长期存下来。
"""

from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime
import re
from zoneinfo import ZoneInfo

from nonebot.adapters import Event
from nonebot_plugin_alconna.uniseg import (
    At,
    AtAll,
    Emoji,
    Image,
    Segment,
    Text,
    UniMessage,
)

from .config import history_config

TZ = ZoneInfo("Asia/Shanghai")

_PEER_SUFFIX = re.compile(r"@(?:group|friend|temp):\d+$")


def message_key(message_id: str) -> str:
    """消息 id 在会话内的写法。

    alconna 给 Milky 消息的 id 带会话后缀（``seq@group:群号``），被回复、发送回执里
    拿到的却只有 ``seq``；缓冲本来就按会话分开，去掉后缀两边才对得上。
    """
    return _PEER_SUFFIX.sub("", message_id)


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
    seq: int = 0
    """会话内的递增编号，进缓冲时分配；模型翻记录时用它指认「从哪条往前翻」"""


def scope_id(event: Event) -> str:
    """消息归属的会话（群/频道/私聊），与 what2eat 的取法保持一致"""
    user_id = event.get_user_id()
    try:
        session_id = event.get_session_id()
    except ValueError:
        return user_id
    # 各适配器的群/频道会话 id 都以 _{user_id} 结尾，去掉后就是会话本身
    return session_id.removesuffix(f"_{user_id}") or user_id


def display_name(source: object) -> str | None:
    """事件或被回复消息（``Reply.origin``）里发送者的展示名，取不到时为 None。

    各适配器把昵称放在不同地方（OneBot 在 ``sender.card/nickname``、Milky 在
    ``data.sender``、QQ 官方在 ``author.username``），没有统一接口，只能按已知的
    字段挨个试。
    """
    data = getattr(source, "data", None)
    owners = (
        getattr(source, "sender", None),
        getattr(source, "author", None),
        getattr(data, "sender", None),  # Milky 的消息事件、被回复消息
    )
    for owner in owners:
        if owner is None:
            continue
        for attr in ("card", "nickname", "username", "name"):
            if value := getattr(owner, attr, None):
                return str(value)
    # Milky 的引用消息段只带一个 sender_name
    if isinstance(data, dict) and (value := data.get("sender_name")):
        return str(value)
    return None


def sender_name(event: Event) -> str:
    """发送者的展示名，取不到时退回用户 id"""
    return display_name(event) or event.get_user_id()


def segment_text(seg: Segment) -> str:
    """单个消息段的文本形式，非文本段落用占位符表示"""
    if isinstance(seg, Text):
        return seg.text
    if isinstance(seg, At):
        return f"@{seg.display or seg.target}"
    if isinstance(seg, AtAll):
        return "@全体成员"
    if isinstance(seg, Emoji):
        return seg.name or "[表情]"
    if isinstance(seg, Image):
        return "[图片]"
    return f"[{seg.__class__.__name__.lower()}]"


def render_text(msg: UniMessage) -> str:
    """把消息渲染成一行纯文本，非文本段落用占位符表示"""
    return " ".join("".join(segment_text(seg) for seg in msg).split())


class Recorder:
    """按会话保留最近若干条消息"""

    def __init__(self, size: int) -> None:
        self.size = size
        self._buffers: dict[str, deque[Record]] = {}
        self._next_seqs: dict[str, int] = {}

    def _buffer(self, scope: str) -> deque[Record]:
        return self._buffers.setdefault(scope, deque(maxlen=self.size))

    def next_seq(self, scope: str) -> int:
        """下一条进缓冲的消息将拿到的编号"""
        return self._next_seqs.get(scope, 1)

    def push(self, scope: str, record: Record) -> None:
        if record.text:
            seq = self.next_seq(scope)
            self._next_seqs[scope] = seq + 1
            self._buffer(scope).append(
                replace(record, seq=seq, message_id=message_key(record.message_id))
            )

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

    def records(self, scope: str) -> list[Record]:
        """缓冲里的全部消息，旧的在前"""
        return list(self._buffers.get(scope, ()))

    def recent(self, scope: str, limit: int) -> list[Record]:
        """最近的消息，旧的在前"""
        return self.records(scope)[-limit:]

    def find(self, scope: str, message_id: str) -> Record | None:
        """按消息 id 找回被回复的那条"""
        if not message_id:
            return None
        buffer = self._buffers.get(scope)
        if not buffer:
            return None
        key = message_key(message_id)
        return next((r for r in buffer if r.message_id == key), None)


recorder = Recorder(history_config.size)
"""全局缓冲：记录钩子写入，各插件拼上下文时读取"""
