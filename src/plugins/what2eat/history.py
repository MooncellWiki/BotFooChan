"""最近推荐记录，用于避免同一会话短时间内反复推荐同样的东西。

只保存在内存里：窗口本来就只有最近几次推荐，重启后丢失无伤大雅。
"""

from collections import deque
from collections.abc import Iterable
import re

MAX_ITEM_LENGTH = 30
"""单条推荐名称保留的最大长度，避免模型把整段话塞进条目里"""

_NOISE = re.compile(r"[\s\W_]+")


def normalize(item: str) -> str:
    """归一化推荐名称，去掉空白与标点后再比较"""
    return _NOISE.sub("", item).lower()


def is_similar(one: str, other: str) -> bool:
    """名称相同，或一个包含另一个（如“拉面”与“兰州拉面”）时视为重复"""
    one, other = normalize(one), normalize(other)
    if not one or not other:
        return False
    short, long = sorted((one, other), key=len)
    return one == other or (len(short) >= 2 and short in long)


def clean(item: str) -> str:
    """清理模型给出的条目：压平空白并截断"""
    return " ".join(item.split())[:MAX_ITEM_LENGTH]


class SuggestionHistory:
    """按会话与推荐类型（吃/喝）记录最近几次给出的条目"""

    def __init__(self, rounds: int) -> None:
        self.rounds = rounds
        """每个会话保留最近多少次推荐"""
        self._records: dict[tuple[str, str], deque[list[str]]] = {}

    def _entries(self, scope: str, kind: str) -> deque[list[str]]:
        return self._records.setdefault(
            (scope, kind), deque(maxlen=max(self.rounds, 0))
        )

    def recent(self, scope: str, kind: str) -> list[str]:
        """最近推荐过的条目，新的在前，同名的只留一份"""
        seen: set[str] = set()
        items: list[str] = []
        for entry in reversed(self._entries(scope, kind)):
            for item in entry:
                if (key := normalize(item)) not in seen:
                    seen.add(key)
                    items.append(item)
        return items

    def duplicates(self, scope: str, kind: str, items: Iterable[str]) -> list[str]:
        """挑出与最近推荐撞车的条目"""
        recent = self.recent(scope, kind)
        return [item for item in items if any(is_similar(item, old) for old in recent)]

    def remember(self, scope: str, kind: str, items: Iterable[str]) -> None:
        """记下这一次推荐的条目"""
        if cleaned := [text for item in items if (text := clean(item))]:
            self._entries(scope, kind).append(cleaned)
