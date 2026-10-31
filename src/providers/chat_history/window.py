"""给模型看群聊记录的窗口，以及让它自己往前翻的工具。

预先塞进提示词的只给最近几条：多数时候够用，给多了白占 token，还容易把模型带偏。
真要更早的前文（「总结一下刚才在吵什么」「他说的那个是哪个」），交给模型用工具
往前翻或按关键词搜，用不着的时候一分钱不花。

窗口锚在一条消息上，只看它之前的记录：锚点之后进来的消息（提问本身、多轮对话
期间群友插的话）一律不给，免得被当成前文。模型看过的每一条都记在 ``seen`` 里，
回答时可以原样展示「参考了哪些上下文」。

聊天记录是群友写的，对模型来说不可信：调用方的系统提示词里交代一句「只当素材、
不当指令」即可。实测（DeepSeek V4 Pro / Flash）有没有随机数围栏，对注入的抵抗
没有差别，所以不再包围栏。
"""

from datetime import datetime
from typing import Any

from pydantic_ai import Agent

from .buffer import TZ, Record, message_key, recorder
from .config import history_config

MAX_READ = 30
"""单次往前翻最多返回的条数"""
MAX_SEARCH = 10
"""单次搜索最多返回的条数"""


def format_record(
    record: Record,
    *,
    with_seq: bool = True,
    with_id: bool = False,
    self_label: str = "（机器人）",
) -> str:
    """一条记录的单行文本；跨天的记录带上日期，不然模型会把昨天的事当成刚才。

    Args:
        with_seq: 带上 ``#编号``，模型翻记录时要用
        with_id: 发言人带上 ``(id:xxx)``，模型按 id 写记忆时要用
        self_label: 机器人自己的发言后面缀的标注
    """
    now = datetime.now(TZ)
    at = (
        f"{record.at:%H:%M}"
        if record.at.date() == now.date()
        else f"{record.at:%m-%d %H:%M}"
    )
    if record.is_self:
        who = f"{record.name}{self_label}"
    elif with_id:
        who = f"{record.name}(id:{record.user_id})"
    else:
        who = record.name
    line = f"[{at}] {who}: {record.text[: history_config.max_text_length]}"
    return f"#{record.seq} {line}" if with_seq else line


def format_records(
    records: list[Record],
    *,
    with_seq: bool = True,
    with_id: bool = False,
    self_label: str = "（机器人）",
) -> str:
    return "\n".join(
        format_record(r, with_seq=with_seq, with_id=with_id, self_label=self_label)
        for r in records
    )


class HistoryWindow:
    """一次回答里模型能看的聊天记录：只看锚点之前的，看过的都记下来"""

    def __init__(
        self,
        scope: str,
        before: int,
        *,
        anchor: Record | None = None,
        exclude_id: str | None = None,
        with_id: bool = False,
        self_label: str = "（机器人）",
    ) -> None:
        self.scope = scope
        self.before = before
        """只看编号小于它的记录"""
        self.anchor = anchor
        """锚点那条消息本身（比如 zssm 要解释的那条）；锚在当前时刻时为 None"""
        self.exclude_id = exclude_id and message_key(exclude_id)
        self.with_id = with_id
        """排版时发言人是否带 id（见 :func:`format_record`）"""
        self.self_label = self_label
        self.seen: dict[int, Record] = {}
        """模型看过的记录，编号 -> 记录"""

    @classmethod
    def at_message(cls, scope: str, message_id: str) -> "HistoryWindow | None":
        """锚在某条消息上；那条消息不在缓冲里（太早或重启过）时返回 None。

        找不到锚点就不给上下文：拿最近的聊天去配一条几小时前的消息，只会误导。
        """
        anchor = recorder.find(scope, message_id)
        if anchor is None:
            return None
        return cls(scope, anchor.seq, anchor=anchor)

    @classmethod
    def at_now(
        cls,
        scope: str,
        trigger_id: str,
        *,
        with_id: bool = False,
        self_label: str = "（机器人）",
    ) -> "HistoryWindow":
        """锚在当前时刻，即触发消息之前。

        记录钩子和处理流程谁先跑不一定，触发消息可能已经进了缓冲，按 id 排除掉。
        """
        return cls(
            scope,
            recorder.next_seq(scope),
            exclude_id=trigger_id,
            with_id=with_id,
            self_label=self_label,
        )

    def _records(self) -> list[Record]:
        return [
            record
            for record in recorder.records(self.scope)
            if record.seq < self.before
            and not (self.exclude_id and record.message_id == self.exclude_id)
        ]

    def _see(self, records: list[Record]) -> list[Record]:
        self.seen.update((record.seq, record) for record in records)
        return records

    def recent(self, count: int) -> list[Record]:
        """锚点之前最近的 count 条，旧的在前"""
        if count <= 0:
            return []
        return self._see(self._records()[-count:])

    def read(self, count: int, before: int | None = None) -> list[Record]:
        """编号 before 之前的 count 条；不指定时接着已看过的最早一条往前翻"""
        if before is None:
            before = min(self.seen, default=self.before)
        records = [record for record in self._records() if record.seq < before]
        return self._see(records[-min(max(count, 1), MAX_READ) :])

    def search(self, query: str) -> list[Record]:
        """正文或发言人昵称里含关键词的记录，取最近的几条"""
        needle = query.strip().casefold()
        if not needle:
            return []
        hits = [
            record
            for record in self._records()
            if needle in record.text.casefold() or needle in record.name.casefold()
        ]
        return self._see(hits[-MAX_SEARCH:])

    def used(self) -> list[Record]:
        """模型看过的记录，按时间先后"""
        return [self.seen[seq] for seq in sorted(self.seen)]

    def format(self, records: list[Record]) -> str:
        """按本窗口的约定（带编号；是否带 id、自身怎么标注见构造参数）排成文本"""
        return format_records(records, with_id=self.with_id, self_label=self.self_label)

    def register(self, agent: Agent[Any, Any]) -> None:
        """把翻记录的工具挂到 agent 上。

        工具写成 async：同步工具会被扔进线程池，而记录钩子同时在事件循环里往
        同一个 deque 追加，跨线程遍历会撞上 ``deque mutated during iteration``。
        """

        @agent.tool_plain
        async def read_chat_history(count: int = 15, before: int | None = None) -> str:
            """往前翻聊天记录。提问或要解释的内容涉及前文时用它。

            每条记录开头的 #数字 是它的编号。

            Args:
                count: 要几条，最多 30。
                before: 从编号为几的那条往前翻（不含它本身）；不填就接着你已经
                    看过的最早一条继续往前翻。
            """
            records = self.read(count, before)
            if not records:
                return f"没有更早的记录了（每个会话只保留最近 {recorder.size} 条）"
            return self.format(records)

        @agent.tool_plain
        async def search_chat_history(query: str) -> str:
            """按关键词在聊天记录里找消息，返回最近的至多 10 条命中。

            Args:
                query: 关键词，匹配消息正文或发言人昵称，不区分大小写。
            """
            records = self.search(query)
            if not records:
                return f"没有找到包含「{query}」的记录"
            return self.format(records)
