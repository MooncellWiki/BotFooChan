"""基于 pydantic-ai 的统一 LLM 调用封装 provider。

项目内插件的模型调用统一通过本 provider 创建 Agent：

- DeepSeek 官方 API 在模型支持时走 OpenAI Responses API 兼容协议（内置联网搜索）
- 其他 OpenAI 兼容服务（硅基流动、OpenRouter 等）走 chat completions 协议
- ``api_type="anthropic"`` 可切到 Anthropic Messages 兼容协议（DeepSeek 官方为
  ``/anthropic`` 端点），同样支持内置联网搜索，但不支持图片输入与 penalty 类参数

服务商与模型的注册方式见 :mod:`.config`。
"""

from collections.abc import Sequence
import re
import time
from typing import Any

import httpx
from nonebot import logger
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.capabilities import NativeTool
from pydantic_ai.messages import ModelMessage, ModelResponse, ThinkingPart
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from pydantic_ai.native_tools import WebSearchTool
from pydantic_ai.output import OutputSpec
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RunUsage

from .config import ApiType as ApiType
from .config import Config as Config
from .config import ModelEndpoint as ModelEndpoint
from .config import list_models as list_models
from .config import llm_config as llm_config
from .config import require_endpoint as require_endpoint
from .config import resolve_endpoint as resolve_endpoint

_model_cache: dict[tuple[str | None, ...], Model] = {}


def get_model(endpoint: ModelEndpoint) -> Model:
    """按端点构建（并缓存）pydantic-ai Model"""
    key = (
        endpoint.name,
        endpoint.base_url,
        endpoint.api_key,
        endpoint.resolved_api_type,
        endpoint.proxy,
    )
    if cached := _model_cache.get(key):
        return cached

    http_client = httpx.AsyncClient(proxy=endpoint.proxy) if endpoint.proxy else None
    api_type = endpoint.resolved_api_type

    model: Model
    if api_type == "anthropic":
        model = AnthropicModel(
            endpoint.name,
            provider=AnthropicProvider(
                base_url=endpoint.resolved_base_url,
                api_key=endpoint.api_key,
                http_client=http_client,
            ),
        )
    else:
        if endpoint.is_deepseek_official:
            openai_provider = DeepSeekProvider(
                api_key=endpoint.api_key, http_client=http_client
            )
        else:
            openai_provider = OpenAIProvider(
                base_url=endpoint.base_url,
                api_key=endpoint.api_key,
                http_client=http_client,
            )
        model_cls = OpenAIResponsesModel if api_type == "responses" else OpenAIChatModel
        model = model_cls(endpoint.name, provider=openai_provider)

    _model_cache[key] = model
    return model


def create_agent[OutputT](
    endpoint: ModelEndpoint,
    *,
    instructions: str | None = None,
    output_type: OutputSpec[OutputT] = str,
    settings: ModelSettings | None = None,
    retries: int = 1,
    web_search: bool = False,
) -> Agent[None, OutputT]:
    """按端点创建 pydantic-ai Agent。

    web_search 启用服务商内置的联网搜索（服务端执行），Responses 与 Anthropic
    协议均支持：DeepSeek 官方分别对应 tools=[{"type": "web_search"}] 与
    tools=[{"type": "web_search_20250305"}]，chat completions 协议没有对应能力。
    """
    capabilities = None
    if web_search:
        api_type = endpoint.resolved_api_type
        if api_type in ("responses", "anthropic"):
            capabilities = [NativeTool(WebSearchTool())]
        else:
            logger.warning(
                f"模型 {endpoint.name} 走 {api_type} 协议，不支持内置联网搜索，已忽略"
            )
    return Agent(
        get_model(endpoint),
        instructions=instructions,
        output_type=output_type,
        model_settings=settings,
        retries=retries,
        capabilities=capabilities,
    )


_THINK_BLOCK = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def _thinking_text(part: ThinkingPart) -> str:
    """取出一个思维链片段的文本。

    Responses 协议下 DeepSeek 官方不生成 summary，思维链以 reasoning_text 形式
    放在 reasoning item 的 content 中，pydantic-ai 会把它归到
    ``provider_details["raw_content"]`` 而非 ``ThinkingPart.content``
    （见 pydantic_ai.models.openai 对 ResponseReasoningItem 的映射），故需回退取值。
    """
    if part.content:
        return part.content
    raw = (part.provider_details or {}).get("raw_content")
    if isinstance(raw, list):
        return "\n".join(str(chunk) for chunk in raw if chunk)
    return ""


def extract_thinking(messages: Sequence[ModelMessage]) -> str:
    """收集模型响应中的思维链内容"""
    chunks = [
        text
        for message in messages
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, ThinkingPart) and (text := _thinking_text(part))
    ]
    return "\n".join(chunks)


def split_inline_thinking(text: str) -> tuple[str, str]:
    """分离正文中内联的 <think> 标签（部分中转服务不单独拆分思维链）"""
    thinking = "\n".join(
        block.strip() for block in _THINK_BLOCK.findall(text) if block.strip()
    )
    content = _THINK_BLOCK.sub("", text).strip()
    return content, thinking


def extract_content_and_thinking(result: AgentRunResult[str]) -> tuple[str, str]:
    """从一次运行结果中提取正文与思维链"""
    content, inline_thinking = split_inline_thinking(result.output)
    thinking = extract_thinking(result.new_messages()) or inline_thinking
    return content, thinking


class UsageTracker:
    """按模型累计一次处理流程中的 token 消耗，并统计总用时

    渲染结果形如::

        --- 5.0s
        deepseek-v4-flash  I:1966 O:383 A:2349 C:1152

    其中 I 为输入、O 为输出、A 为合计、C 为命中缓存的输入 token。
    """

    def __init__(self) -> None:
        self.started_at = time.perf_counter()
        self.usages: dict[str, RunUsage] = {}

    def record(self, model: str, result: AgentRunResult[Any]) -> None:
        """记录一次模型调用的用量"""
        self.usages.setdefault(model, RunUsage()).incr(result.usage)

    @property
    def elapsed(self) -> float:
        """从创建到当前的耗时（秒）"""
        return time.perf_counter() - self.started_at

    def render(self) -> str:
        """渲染用时与各模型的 token 统计"""
        lines = [f"--- {self.elapsed:.1f}s"]
        for model, usage in self.usages.items():
            stats = [
                f"I:{usage.input_tokens}",
                f"O:{usage.output_tokens}",
                f"A:{usage.total_tokens}",
            ]
            if usage.cache_read_tokens:
                stats.append(f"C:{usage.cache_read_tokens}")
            lines.append(f"{model}  {' '.join(stats)}")
        return "\n".join(lines)
