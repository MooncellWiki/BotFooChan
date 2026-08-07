from collections.abc import Awaitable, Callable
import importlib
from typing import Literal

import httpx
from nonebot import logger
from nonebot.adapters import Event
from nonebot.matcher import Matcher, current_event, current_matcher
from nonebot.permission import Permission, User
from nonebot_plugin_alconna import SupportAdapter
from nonebot_plugin_alconna.uniseg import (
    UniMessage,
    UniMsg,
    get_message_id,
    get_target,
    message_reaction,
)
from nonebot_plugin_waiter import Waiter, prompt
from openai import APIConnectionError, APITimeoutError
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from src.libs.llm import create_agent, extract_content_and_thinking

from .config import CustomModel, ds_config


class DeepSeekHandler:
    def __init__(
        self, model: CustomModel, is_to_pic: bool, is_contextual: bool
    ) -> None:
        self.model = model
        self.is_to_pic = is_to_pic
        self.is_contextual = is_contextual
        self.agent: Agent[None, str] = create_agent(
            model.to_endpoint(),
            instructions=model.prompt or ds_config.prompt or None,
            settings=model.to_settings(ds_config.api_timeout),
            web_search=model.web_search,
        )
        self.history: list[ModelMessage] = []
        self.pending: str | None = None
        self.event: Event = current_event.get()
        self.matcher: Matcher = current_matcher.get()
        self.message_id: str = get_message_id(self.event)
        self.waiter: Waiter[str | Literal[False]] = self._setup_waiter()

        self.md_to_pic: Callable[..., Awaitable[bytes]] | None = (
            importlib.import_module("nonebot_plugin_htmlrender").md_to_pic
            if self.is_to_pic
            else None
        )

    async def handle(self, content: str | None) -> None:
        if not self.is_contextual and content is None:
            await UniMessage.text("请输入内容，例：/deepseek 你好").finish(
                reply_to=self.message_id
            )

        self.pending = content
        await self._message_reaction("thinking")

        if self.is_contextual:
            await self._handle_multi_round()
        else:
            await self._handle_single()

    async def _handle_single(self) -> None:
        assert self.pending is not None
        if result := await self._run(self.pending):
            await self._send_response(result)

    async def _handle_multi_round(self) -> None:
        async for resp in self.waiter(default=False, timeout=ds_config.input_timeout):
            text = await self._resolve_input(resp)
            if text is None:
                continue
            result = await self._run(text)
            if result is None:
                continue
            await self._send_response(result)

    def _setup_waiter(self) -> Waiter[str | Literal[False]]:
        permission = Permission(
            User.from_event(self.event, perm=self.matcher.permission)
        )
        waiter = Waiter(
            waits=["message"],
            handler=self._waiter_handler,
            matcher=self.matcher,
            permission=permission,
        )
        waiter.future.set_result("")
        return waiter

    def _waiter_handler(self, msg: UniMsg, skip: bool = False) -> str | Literal[False]:
        text = msg.extract_plain_text()
        if not skip:
            self.message_id = get_message_id()
        if text in ("结束", "取消", "done"):
            return False
        if text in ("回滚", "rollback"):
            return "rollback"
        return text

    def _prompt_handler(self, msg: UniMsg) -> UniMsg:
        self.message_id = get_message_id()
        return msg

    async def _resolve_input(self, resp: str | bool) -> str | None:
        if resp == "":
            if self.pending is not None:
                text, self.pending = self.pending, None
                await self._message_reaction("thinking")
                return text
            if not self.history:
                _resp = await prompt(
                    "你想对 DeepSeek 说什么呢？",
                    handler=self._prompt_handler,
                    timeout=ds_config.input_timeout,
                )
                if _resp is None:
                    await UniMessage.text("等待超时").finish(reply_to=self.message_id)
                resp = self._waiter_handler(_resp, skip=True)

        await self._message_reaction("thinking")

        if isinstance(resp, bool):
            await UniMessage.text("已结束对话").finish(reply_to=self.message_id)
        if resp == "rollback":
            await self._handle_rollback()
            return None
        return resp or None

    async def _run(self, text: str) -> AgentRunResult[str] | None:
        try:
            result = await self.agent.run(text, message_history=self.history or None)
        except Exception as e:
            logger.opt(exception=e).error("DeepSeek 请求失败")
            await self._message_reaction("fail")
            if not self.is_contextual:
                await UniMessage.text(self._describe_error(e)).finish(
                    reply_to=self.message_id
                )
            await UniMessage.text(f"Oops! {self._describe_error(e)}，请重新输入").send(
                reply_to=self.message_id
            )
            return None

        self.history = result.all_messages()
        return result

    @staticmethod
    def _describe_error(e: Exception) -> str:
        if isinstance(e, APITimeoutError | httpx.TimeoutException):
            return "网络超时，请稍后重试"
        if isinstance(e, APIConnectionError | httpx.RequestError):
            return "连接异常，请稍后重试"
        if isinstance(e, ModelHTTPError):
            return f"请求失败（{e.status_code}）: {e.body or ''}"
        return f"请求失败: {e}"

    async def _handle_rollback(self) -> None:
        if len(self.history) >= 2:
            self.history = self.history[:-2]
            remaining = self._last_context_text() or "空"
            await UniMessage.text(
                f"已回滚 1 轮对话。当前上下文为:\n{remaining}\nuser:（等待输入）"
            ).send(reply_to=self.message_id)
        else:
            await UniMessage.text("无法回滚，当前对话记录为空").send(
                reply_to=self.message_id
            )

    def _last_context_text(self) -> str:
        if not self.history:
            return ""
        last = self.history[-1]
        if isinstance(last, ModelResponse):
            text = "".join(
                part.content for part in last.parts if isinstance(part, TextPart)
            )
            return f"assistant: {text}"
        text = "".join(
            part.content
            for part in last.parts
            if isinstance(part, UserPromptPart) and isinstance(part.content, str)
        )
        return f"user: {text}"

    async def _message_reaction(
        self, status: Literal["fail", "thinking", "done"]
    ) -> None:
        emoji_map = {
            "fail": ["10060", "❌"],
            "thinking": ["424", "👀"],
            "done": ["144", "🎉"],
        }
        target = get_target(self.event)
        if is_qq := target.adapter in (SupportAdapter.onebot11, SupportAdapter.qq):
            emoji = emoji_map[status][0]
        else:
            emoji = emoji_map[status][1]

        if is_qq and target.private:
            return

        await message_reaction(emoji, message_id=self.message_id)

    async def _send_response(self, result: AgentRunResult[str]) -> None:
        content, thinking = extract_content_and_thinking(result)

        output = content
        if ds_config.enable_send_thinking and content and thinking:
            output = (
                f"<blockquote><p>{thinking}</p></blockquote>{content}"
                if self.is_to_pic
                else f"{thinking}\n\n--------------------\n\n{content}"
            )

        await self._message_reaction("done")

        if self.md_to_pic is not None:
            await UniMessage.image(raw=await self.md_to_pic(output)).send(
                reply_to=self.message_id
            )
        else:
            await UniMessage.text(output).send(reply_to=self.message_id)
