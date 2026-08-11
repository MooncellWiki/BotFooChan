"""全局用户记忆 provider。

以用户为粒度维护一份**自由格式的 markdown 档案**，跨群、跨适配器共用同一份：
写入方（通用对话插件里的 LLM 工具、memory 插件的管理指令）改的都是这份文档，
读取方（what2eat、通用对话）直接把文档原文塞进提示词。

不拆成 region / preferences 之类的字段：记忆最终总要以文本进提示词，中间那层
结构化只是「先拆开、再拼回文本」的损耗，还会把「在做什么项目」「说话风格」
这类事先设计不出来的信息挡在门外。文档过长时由 :mod:`.compress` 主动压缩。
"""

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime

from nonebot import logger, require

require("nonebot_plugin_orm")
from nonebot_plugin_orm import Model, get_session
from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from .compress import compress as compress
from .compress import trim as trim
from .config import memory_config as memory_config

EMPTY_HINT = "（暂无记录）"
"""档案为空时用于提示词的占位文本"""


class UserMemory(Model):
    """一位用户的记忆档案"""

    __tablename__ = "user_memory"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    """事件里的用户 ID（``Event.get_user_id()``）"""
    content: Mapped[str] = mapped_column(Text, default="")
    """自由格式的 markdown 档案正文"""
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """最后一次写入时间"""


_locks: dict[str, asyncio.Lock] = {}
"""按用户串行化写入：一轮对话里模型可能连着写好几条，避免相互覆盖"""


def _lock(user_id: str) -> asyncio.Lock:
    return _locks.setdefault(user_id, asyncio.Lock())


async def get_memory(user_id: str) -> str:
    """读取档案正文；没有记录时返回空串"""
    async with get_session() as session:
        memory = await session.get(UserMemory, user_id)
        return memory.content if memory else ""


async def get_memories(user_ids: Iterable[str]) -> dict[str, str]:
    """批量读取档案，只返回有内容的那些（用于给对话拼上下文）"""
    ids = list(dict.fromkeys(user_ids))
    if not ids:
        return {}
    async with get_session() as session:
        rows = await session.scalars(
            select(UserMemory).where(UserMemory.user_id.in_(ids))
        )
        return {row.user_id: row.content for row in rows if row.content.strip()}


async def _write(user_id: str, content: str) -> str:
    """落库，过长时先压缩。调用方需自行持有该用户的锁"""
    content = content.strip()
    if len(content) > memory_config.max_chars:
        logger.debug(f"用户 {user_id} 的记忆有 {len(content)} 字，触发压缩")
        content = (await compress(content)).strip()

    async with get_session() as session:
        memory = await session.get(UserMemory, user_id)
        if memory is None:
            session.add(
                UserMemory(
                    user_id=user_id, content=content, updated_at=datetime.now(UTC)
                )
            )
        else:
            memory.content = content
            memory.updated_at = datetime.now(UTC)
        await session.commit()
    return content


async def set_memory(user_id: str, content: str) -> str:
    """整份覆盖档案，返回实际落库的内容（可能已被压缩）"""
    async with _lock(user_id):
        return await _write(user_id, content)


async def append_memory(user_id: str, note: str) -> str:
    """追加一条记忆，返回追加后的完整档案。

    重复的条目直接跳过：模型经常在同一轮里把已经知道的事再写一遍。
    """
    note = " ".join(note.split())
    if not note:
        raise ValueError("记忆内容不能为空")

    async with _lock(user_id):
        async with get_session() as session:
            memory = await session.get(UserMemory, user_id)
            current = memory.content if memory else ""

        entry = note if note.startswith("- ") else f"- {note}"
        if any(line.strip() == entry for line in current.splitlines()):
            return current

        return await _write(user_id, f"{current}\n{entry}" if current else entry)


async def replace_memory(user_id: str, old: str, new: str) -> str | None:
    """把 ``old`` 命中的那一条记忆整条换成 ``new``（``new`` 为空即删除该条）。

    按**整行**替换，而不是按子串：模型常常只记得条目的一个片段，拿片段做子串
    替换会把「广州人，在天河上班」改成「广州人，在搬到番禺了上班」这种半截话，
    只有整条换掉才是它真正想表达的意思。

    没命中、或者命中多条时返回 None，让调用方把失败如实回给模型而不是静默吞掉。
    """
    old = old.strip()
    if not old:
        raise ValueError("待替换的内容不能为空")

    async with _lock(user_id):
        async with get_session() as session:
            memory = await session.get(UserMemory, user_id)
            current = memory.content if memory else ""

        lines = current.splitlines()
        needle = old.removeprefix("- ").strip()
        # 先按整条精确匹配，不中再退一步找唯一包含它的那条
        targets = [
            index
            for index, line in enumerate(lines)
            if line.removeprefix("- ").strip() == needle
        ]
        if not targets:
            targets = [
                index for index, line in enumerate(lines) if needle and needle in line
            ]
        if len(targets) != 1:
            return None

        new = " ".join(new.split())
        if new:
            lines[targets[0]] = new if new.startswith("- ") else f"- {new}"
        else:
            del lines[targets[0]]

        return await _write(user_id, "\n".join(line for line in lines if line.strip()))


async def clear_memory(user_id: str) -> bool:
    """删除档案；本来就没有记录时返回 False"""
    async with _lock(user_id):
        async with get_session() as session:
            memory = await session.get(UserMemory, user_id)
            if memory is None:
                return False
            await session.delete(memory)
            await session.commit()
            return True
