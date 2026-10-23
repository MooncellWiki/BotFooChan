"""SQLite 下代替 Postgres JSONB 的列类型。

原版 user / group / subscriber 这几列是 JSONB：按值比较，还能在上面建唯一索引。
SQLite 的 JSON 列存的只是一段文本，比较也是逐字比较——键的顺序、空白不一样，
同一个对象就对不上了（bison 的订阅者匹配就踩过这个坑）。

这里在落库前统一成「键排好序、没有多余空白」的写法，让同一个对象只有一种文本，
等值查询和唯一约束才靠得住；读出来时再还原成 dict，上层用法与原版一致。
"""

import json
from typing import Any

from sqlalchemy import Dialect, String
from sqlalchemy.types import TypeDecorator


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class CanonicalJSON(TypeDecorator[dict[str, Any]]):
    impl = String
    cache_ok = True

    def process_bind_param(
        self, value: dict[str, Any] | None, dialect: Dialect
    ) -> str | None:
        return None if value is None else canonical_json(value)

    def process_result_value(
        self, value: str | None, dialect: Dialect
    ) -> dict[str, Any] | None:
        return None if value is None else json.loads(value)
