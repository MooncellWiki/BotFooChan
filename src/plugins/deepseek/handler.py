from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import httpx
from nonebot import logger
from nonebot.adapters import Event
from nonebot.matcher import Matcher, current_event, current_matcher
from nonebot.permission import Permission, User
from nonebot_plugin_alconna import SupportAdapter
from nonebot_plugin_alconna.uniseg import (
    Image,
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
from pydantic_ai.messages import ModelMessage, UserContent

from src.providers.llm import ModelEndpoint, create_agent
from src.providers.llm.media import as_model_inputs
from src.providers.llm.transcript import Section, build_sections, render_transcript

from .binding import GroupBinding, group_bindings
from .config import CustomModel, ds_config
from .markdown import send_group_markdown

if TYPE_CHECKING:
    from nonebot_plugin_htmlrender import RenderedImage


@dataclass
class UserInput:
    """一次提问：正文加上随消息发来的图片"""

    text: str = ""
    images: list[Image] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.text or self.images)


WaiterResult = UserInput | Literal[False, "rollback"]
"""多轮对话里一条消息的解析结果：提问 / 结束 / 回滚"""


class DeepSeekHandler:
    def __init__(
        self,
        model: CustomModel,
        is_to_pic: bool,
        is_contextual: bool,
        allow_group_markdown: bool = True,
    ) -> None:
        self.model = model
        self.is_to_pic = is_to_pic
        self.is_contextual = is_contextual
        self.allow_group_markdown = allow_group_markdown
        """群聊里优先用官方机器人发原生 markdown；显式 -r 指定渲染时置 False"""
        self.endpoint: ModelEndpoint = model.to_endpoint()
        self.agent: Agent[None, str] = create_agent(
            self.endpoint,
            instructions=model.prompt or ds_config.prompt or None,
            settings=model.to_settings(ds_config.api_timeout),
            web_search=model.web_search,
        )
        self.history: list[ModelMessage] = []
        self.pending: UserInput | None = None
        self.event: Event = current_event.get()
        self.matcher: Matcher = current_matcher.get()
        self.message_id: str = get_message_id(self.event)
        self.waiter: Waiter[WaiterResult] = self._setup_waiter()

        self.render_chat: Callable[..., Awaitable["RenderedImage"]] | None = None
        if self.is_to_pic:
            # 延迟导入：htmlrender 是可选依赖，插件入口用 find_spec 判断过才会走到这里
            from src.providers.llm.chat import render_chat

            self.render_chat = render_chat

    async def handle(self, content: str | None, images: Sequence[Image] = ()) -> None:
        user_input = UserInput(content or "", list(images))
        if not self.is_contextual and not user_input:
            await UniMessage.text("请输入内容或发送图片，例：/deepseek 你好").finish(
                reply_to=self.message_id
            )

        self.pending = user_input or None
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
            user_input = await self._resolve_input(resp)
            if user_input is None:
                continue
            result = await self._run(user_input)
            if result is None:
                continue
            await self._send_response(result)

    def _setup_waiter(self) -> Waiter[WaiterResult]:
        permission = Permission(
            User.from_event(self.event, perm=self.matcher.permission)
        )
        waiter = Waiter(
            waits=["message"],
            handler=self._waiter_handler,
            matcher=self.matcher,
            permission=permission,
        )
        # 空提问是首轮的占位，让循环先把命令自带的提问消费掉
        waiter.future.set_result(UserInput())
        return waiter

    def _waiter_handler(self, msg: UniMsg, skip: bool = False) -> WaiterResult:
        text = msg.extract_plain_text().strip()
        if not skip:
            self.message_id = get_message_id()
        if text in ("结束", "取消", "done"):
            return False
        if text in ("回滚", "rollback"):
            return "rollback"
        return UserInput(text, list(msg.get(Image)))

    def _prompt_handler(self, msg: UniMsg) -> UniMsg:
        self.message_id = get_message_id()
        return msg

    async def _resolve_input(self, resp: WaiterResult | bool) -> UserInput | None:
        # 空提问既是首轮的占位，也可能是用户发了条没有内容的消息
        if isinstance(resp, UserInput) and not resp:
            if self.pending is not None:
                pending, self.pending = self.pending, None
                await self._message_reaction("thinking")
                return pending
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

    async def _note(self, text: str) -> None:
        await UniMessage.text(text).send(reply_to=self.message_id)

    async def _build_prompt(
        self, user_input: UserInput
    ) -> str | list[UserContent] | None:
        """提问 -> 模型输入；图片用不上时降级成纯文本，两头都空则返回 None"""
        images = await self._image_inputs(user_input.images)
        if not images:
            return user_input.text or None
        return [user_input.text, *images] if user_input.text else images

    async def _image_inputs(self, images: Sequence[Image]) -> list[UserContent]:
        """把图片取回来交给模型；模型不认或取不到时说一声并退化成纯文本"""
        limit = ds_config.max_images
        if not images:
            return []
        if not self.endpoint.supports_vision:
            await self._note(f"{self.model.display_name} 不支持图片输入，已忽略图片")
            return []
        if limit <= 0:
            await self._note("图片输入已关闭，已忽略图片")
            return []

        contents = await as_model_inputs(images, limit=limit)
        if not contents:
            await self._note("图片获取失败，已忽略图片")
        elif dropped := len(images) - len(contents):
            await self._note(f"已忽略 {dropped} 张图片（超出 {limit} 张上限或取不到）")
        return list(contents)

    async def _run(self, user_input: UserInput) -> AgentRunResult[str] | None:
        content = await self._build_prompt(user_input)
        if content is None:
            # 图片全军覆没且没有正文，提示已经在 _image_inputs 里发过了
            await self._message_reaction("fail")
            return None

        try:
            result = await self.agent.run(content, message_history=self.history or None)
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
                f"已回滚 1 轮对话。当前上下文为:\n{remaining}\n【🧑 用户】（等待输入）"
            ).send(reply_to=self.message_id)
        else:
            await UniMessage.text("无法回滚，当前对话记录为空").send(
                reply_to=self.message_id
            )

    def _last_context_text(self) -> str:
        """回滚后回显剩下的最后一条消息，图片提问也能交代清楚"""
        if not self.history:
            return ""
        return render_transcript(build_sections(self.history[-1:]), flavor="text")

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

    def _group_binding(self) -> GroupBinding | None:
        """当前群是否登记了官方机器人的 group_openid"""
        if not self.allow_group_markdown:
            return None

        target = get_target(self.event)
        if target.private or target.adapter != SupportAdapter.onebot11:
            return None
        return group_bindings.get(target.id)

    async def _send_response(self, result: AgentRunResult[str]) -> None:
        sections: list[Section] = build_sections(
            result.new_messages(), with_thinking=ds_config.enable_send_thinking
        )
        binding = self._group_binding()

        await self._message_reaction("done")

        # 官方接口有主动消息额度、原生 markdown 权限等限制，发不出去就退回原路径
        if binding is not None and await send_group_markdown(
            binding,
            render_transcript(sections, flavor="markdown", fallback=result.output),
        ):
            return

        if self.render_chat is not None:
            rendered = await self.render_chat(sections, fallback=result.output)
            await UniMessage.image(raw=rendered.data).send(reply_to=self.message_id)
        else:
            await UniMessage.text(
                render_transcript(sections, flavor="text", fallback=result.output)
            ).send(reply_to=self.message_id)
