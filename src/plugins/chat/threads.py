"""机器人每条回答对应的对话记录：有人回复这条回答，就从这里接着聊。

取代原先 ``/ds --with-context`` 的等待式多轮——那种做法在对话期间把发起人的每条
消息都当成提问，60 秒不说话就散。这里谁也不占着：回复哪条回答就从哪条接，几个人
各自回复同一条回答也互不干扰（各自分叉出去）。

只放内存：重启后找不到记录的回复会被当成普通的引用消息处理。
"""

from collections import OrderedDict
import time

from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart

MAX_THREADS = 200
"""最多记住多少条回答的对话记录，超出后丢掉最久没用的"""
TTL = 6 * 60 * 60
"""一段对话多久没人接就作废（秒）"""
MAX_TURNS = 20
"""一段对话最多保留的轮数，再往前的丢掉，免得越聊越贵"""


def _trim(messages: list[ModelMessage]) -> list[ModelMessage]:
    """只留最近 MAX_TURNS 轮。

    从某一轮提问处整段切开：一轮里的工具调用与工具结果必须成对出现，
    从中间切会让服务商直接拒绝请求。
    """
    starts = [
        i
        for i, message in enumerate(messages)
        if isinstance(message, ModelRequest)
        and any(isinstance(part, UserPromptPart) for part in message.parts)
    ]
    if len(starts) <= MAX_TURNS:
        return messages
    return messages[starts[-MAX_TURNS] :]


class ThreadStore:
    def __init__(self) -> None:
        self._threads: OrderedDict[
            tuple[str, str], tuple[float, list[ModelMessage]]
        ] = OrderedDict()

    def get(self, scope: str, message_id: str) -> list[ModelMessage] | None:
        """被回复的那条回答之前的对话记录；不是机器人的回答或已过期时为 None"""
        key = (scope, message_id)
        if (item := self._threads.get(key)) is None:
            return None
        saved_at, messages = item
        if time.monotonic() - saved_at > TTL:
            del self._threads[key]
            return None
        self._threads.move_to_end(key)
        return messages

    def save(self, scope: str, message_id: str, messages: list[ModelMessage]) -> None:
        """记下截至这条回答的对话；拿不到回答的消息 id 时无从接续，不记"""
        if not message_id:
            return
        key = (scope, message_id)
        self._threads[key] = (time.monotonic(), _trim(messages))
        self._threads.move_to_end(key)
        while len(self._threads) > MAX_THREADS:
            self._threads.popitem(last=False)


threads = ThreadStore()
