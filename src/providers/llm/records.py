"""LLM 调用记录：每次 agent.run 记一条，管理后台的「调用记录」页看。

:func:`.create_agent` 给每个 Agent 挂上 :class:`RecordingCapability`，包住整个运行：
计时、取 token 用量、把这次新增的消息存下来，出错也记一条。调用方不用改。

是哪个插件、哪个会话发起的，从 NoneBot 当前事件的 ContextVar 里取；后台任务之类
不在事件处理里的调用，这些字段为空，功能名由 create_agent 的 task 参数补上。

对话内容里有群聊上下文和群友档案，保留期（默认 30 天）一过就清掉，只留用量和耗时；
记录本身默认留 180 天。图片等二进制内容从来不存。
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import time
from typing import Any

from nonebot import get_driver, logger, require
from nonebot.matcher import current_bot, current_event, current_matcher
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.capabilities.abstract import WrapRunHandler
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.run import AgentRunResult
from pydantic_ai.usage import RunUsage

require("nonebot_plugin_orm")
from nonebot_plugin_orm import Model, get_session
from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, delete, update
from sqlalchemy.orm import Mapped, mapped_column

from src.providers.settings import register

from .config import ModelEndpoint

MAX_TEXT = 20_000
"""单个字符串最多存多长（抓下来的网页之类），超出截断"""
PURGE_INTERVAL = 6 * 60 * 60
"""多久清理一次过期内容（秒）"""


class RecordsConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    enabled: bool = True
    """记录每次模型调用（用量、耗时、状态）"""
    store_messages: bool = True
    """同时存下对话内容（提示词、上下文、工具结果、回答），在后台能回放；关掉只记用量"""
    content_days: int = Field(default=30, ge=1)
    """对话内容保留几天，过期只清内容、保留用量"""
    keep_days: int = Field(default=180, ge=1)
    """记录本身保留几天"""


records_config = register(
    "llm_records",
    RecordsConfig,
    title="调用记录",
    description="LLM 调用的用量、耗时和对话内容的记录与保留期",
    env=RecordsConfig,
)


class LLMInvocation(Model):
    __tablename__ = "llm_invocation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    task: Mapped[str] = mapped_column(String(64), index=True)
    """功能：发起调用的插件名，或 create_agent 传的 task"""
    adapter: Mapped[str | None] = mapped_column(String(32))
    bot_id: Mapped[str | None] = mapped_column(String(64))
    session_id: Mapped[str | None] = mapped_column(String(256), index=True)
    user_id: Mapped[str | None] = mapped_column(String(128))
    model_alias: Mapped[str | None] = mapped_column(String(128))
    provider: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(128))
    api_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), index=True)
    """ok / error / cancelled"""
    error: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    web_search: Mapped[bool] = mapped_column(Boolean, default=False)
    output_preview: Mapped[str] = mapped_column(Text, default="")
    messages: Mapped[list[Any] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )
    """这次运行新增的消息（pydantic-ai 的 JSON 格式），过了保留期置空"""


def _event_context() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    try:
        out["plugin"] = current_matcher.get().plugin_name
    except LookupError:
        pass
    try:
        bot = current_bot.get()
        out["adapter"] = bot.adapter.get_name()
        out["bot_id"] = bot.self_id
    except LookupError:
        pass
    try:
        event = current_event.get()
    except LookupError:
        return out
    for key, getter in (
        ("session_id", event.get_session_id),
        ("user_id", event.get_user_id),
    ):
        try:
            out[key] = getter()
        except Exception:
            pass
    return out


def _shrink(value: Any) -> Any:
    """去掉二进制内容、截断过长的字符串"""
    if isinstance(value, dict):
        if value.get("kind") == "binary" and isinstance(value.get("data"), str):
            return {**value, "data": "", "stripped_size": len(value["data"])}
        return {k: _shrink(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_shrink(v) for v in value]
    if isinstance(value, str) and len(value) > MAX_TEXT:
        return value[:MAX_TEXT] + f"…（已截断，原长 {len(value)}）"
    return value


def dump_messages(messages: Sequence[ModelMessage]) -> list[Any]:
    return _shrink(ModelMessagesTypeAdapter.dump_python(list(messages), mode="json"))


def load_messages(data: list[Any]) -> list[ModelMessage]:
    return ModelMessagesTypeAdapter.validate_python(data)


_pending: set[asyncio.Task[None]] = set()


async def _insert(row: LLMInvocation) -> None:
    try:
        async with get_session() as session:
            session.add(row)
            await session.commit()
    except Exception as e:
        logger.opt(exception=e).warning("LLM 调用记录写库失败")


@dataclass
class RecordingCapability(AbstractCapability[Any]):
    """包住一次 Agent 运行，结束后写一条调用记录"""

    endpoint: ModelEndpoint
    task: str | None = None
    web_search: bool = False

    def _record(
        self,
        started: float,
        status: str,
        usage: RunUsage,
        *,
        context: dict[str, str | None],
        messages: Sequence[ModelMessage] = (),
        output: Any = None,
        error: BaseException | None = None,
    ) -> None:
        row = LLMInvocation(
            created_at=datetime.now(UTC),
            task=self.task or context.get("plugin") or "unknown",
            adapter=context.get("adapter"),
            bot_id=context.get("bot_id"),
            session_id=context.get("session_id"),
            user_id=context.get("user_id"),
            model_alias=self.endpoint.alias,
            provider=self.endpoint.provider,
            model_name=self.endpoint.name,
            api_type=self.endpoint.resolved_api_type,
            status=status,
            error=f"{type(error).__name__}: {error}"[:4000] if error else None,
            latency_ms=int((time.perf_counter() - started) * 1000),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            requests=usage.requests,
            tool_calls=usage.tool_calls,
            web_search=self.web_search,
            output_preview=("" if output is None else str(output))[:500],
            messages=(
                dump_messages(messages)
                if records_config.store_messages and messages
                else None
            ),
        )
        task = asyncio.create_task(_insert(row))
        _pending.add(task)
        task.add_done_callback(_pending.discard)

    async def wrap_run(
        self, ctx: RunContext[Any], *, handler: WrapRunHandler
    ) -> AgentRunResult[Any]:
        if not records_config.enabled:
            return await handler()
        context = _event_context()
        started = time.perf_counter()
        history = len(ctx.messages)
        try:
            result = await handler()
        except asyncio.CancelledError as e:
            self._record(started, "cancelled", ctx.usage, context=context, error=e)
            raise
        except Exception as e:
            self._record(
                started,
                "error",
                ctx.usage,
                context=context,
                messages=ctx.messages[history:],
                error=e,
            )
            raise
        try:
            self._record(
                started,
                "ok",
                result.usage,
                context=context,
                messages=result.new_messages(),
                output=result.output,
            )
        except Exception as e:
            logger.opt(exception=e).warning("LLM 调用记录整理失败")
        return result


async def purge() -> tuple[int, int]:
    """清掉过了保留期的对话内容和记录，返回 (清了内容的条数, 删掉的条数)"""
    now = datetime.now(UTC)
    content_before = now - timedelta(days=records_config.content_days)
    keep_before = now - timedelta(days=records_config.keep_days)
    async with get_session() as session:
        cleared = await session.execute(
            update(LLMInvocation)
            .where(
                LLMInvocation.created_at < content_before,
                LLMInvocation.messages.is_not(None),
            )
            .values(messages=None)
        )
        deleted = await session.execute(
            delete(LLMInvocation).where(LLMInvocation.created_at < keep_before)
        )
        await session.commit()
    return cleared.rowcount, deleted.rowcount  # pyright: ignore[reportAttributeAccessIssue]


async def _purge_forever() -> None:
    while True:
        try:
            cleared, deleted = await purge()
            if cleared or deleted:
                logger.info(f"LLM 调用记录：清掉 {cleared} 条的内容，删掉 {deleted} 条")
        except Exception as e:
            logger.opt(exception=e).warning("清理 LLM 调用记录失败")
        await asyncio.sleep(PURGE_INTERVAL)


_purger: asyncio.Task[None] | None = None


@get_driver().on_startup
async def _start_purger() -> None:
    global _purger
    _purger = asyncio.create_task(_purge_forever())


@get_driver().on_shutdown
async def _stop_purger() -> None:
    if _purger is not None:
        _purger.cancel()
    if _pending:
        await asyncio.gather(*_pending, return_exceptions=True)
