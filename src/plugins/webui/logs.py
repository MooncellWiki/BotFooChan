"""最近的日志留在内存里给后台看：环形缓冲，只收 INFO 及以上。

DEBUG 级别会把整份配置连同密钥打出来，不能收。

单进程部署，缓冲就在这个进程里；重启后清空。前端按 id 增量拉取。
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import logging
import re
import traceback
from typing import TYPE_CHECKING

from nonebot import logger

if TYPE_CHECKING:
    from loguru import Message

CAPACITY = 2000
MIN_LEVEL = "INFO"

# logger.opt(colors=True) 的消息里带着 loguru 的颜色标签，去掉免得满屏 <y>
_COLOR_TAG = re.compile(
    r"</?(?:[rgybmcwekRGYBMCWEK]|l[rgybmcwe]|bold|dim|normal|italic|underline|strike"
    r"|reverse|blink|hide|level|lvl|red|green|yellow|blue|magenta|cyan|white|black"
    r"|light-\w+|fg [^>]+|bg [^>]+)>"
)


@dataclass(frozen=True, slots=True)
class LogEntry:
    id: int
    time: datetime
    level: str
    level_no: int
    name: str
    message: str


_entries: deque[LogEntry] = deque(maxlen=CAPACITY)
_next_id = 1


def _sink(message: "Message") -> None:
    global _next_id
    record = message.record
    text = _COLOR_TAG.sub("", record["message"])
    if (exc := record["exception"]) is not None and exc.type is not None:
        text += (
            "\n"
            + "".join(traceback.format_exception(exc.type, exc.value, exc.traceback))[
                -4000:
            ]
        )
    _entries.append(
        LogEntry(
            id=_next_id,
            time=record["time"],
            level=record["level"].name,
            level_no=record["level"].no,
            name=record["name"] or "",
            message=text,
        )
    )
    _next_id += 1


class _DropPolling(logging.Filter):
    """日志页每 2 秒拉一次 /admin/api/logs，这些访问日志不记，免得刷屏"""

    def filter(self, record: logging.LogRecord) -> bool:
        return "/admin/api/logs" not in record.getMessage()


def install() -> None:
    for name in ("uvicorn.access", "gunicorn.access"):
        logging.getLogger(name).addFilter(_DropPolling())
    logger.add(
        _sink, level=MIN_LEVEL, format="{message}", backtrace=False, diagnose=False
    )


def entries(after: int = 0) -> list[LogEntry]:
    return [e for e in _entries if e.id > after]
