"""基于 pydantic-ai 的统一 LLM 调用封装。

项目内插件的模型调用统一通过本模块创建 Agent：

- DeepSeek 官方 API 在模型支持时走 OpenAI Responses API 兼容协议（内置联网搜索）
- 其他 OpenAI 兼容服务（硅基流动、OpenRouter 等）走 chat completions 协议
- ``api_type="anthropic"`` 可切到 Anthropic Messages 兼容协议（DeepSeek 官方为
  ``/anthropic`` 端点），同样支持内置联网搜索，但不支持图片输入与 penalty 类参数

服务商与模型统一在全局配置中注册，各插件只持有一个模型引用：

- ``LLM__PROVIDERS``：服务商注册表，``名称 -> {base_url, api_key, ...}``，Key 只配置一次
- ``LLM__MODELS``：模型注册表，``别名 -> "服务商:模型名"``（或对象形式以覆写协议等字段）

插件配置中的模型引用既可以是注册表别名，也可以直接写 ``服务商:模型名``。
"""

from collections.abc import Sequence
from functools import cache
import re
import time
from typing import Any, Literal

import httpx
from nonebot import get_plugin_config, logger
from pydantic import BaseModel, Field, field_validator
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

DEEPSEEK_OFFICIAL_HOST = "api.deepseek.com"
DEEPSEEK_ANTHROPIC_PATH = "/anthropic"

ApiType = Literal["responses", "chat", "anthropic"]


def _deepseek_supports_responses(model_name: str) -> bool:
    """DeepSeek 官方 Responses API 目前仅开放 deepseek-v4-flash。

    deepseek-v4-pro 调用 /responses 会返回 400（官方称 2026 年 8 月初支持），
    因此未列入的模型默认回落到 chat completions；待官方放开后可移除本函数。
    见 https://api-docs.deepseek.com/zh-cn/guides/responses_api
    """
    return model_name.startswith("deepseek-v4-flash")


class ModelEndpoint(BaseModel):
    """描述一个可调用的模型端点（模型名 + 服务地址 + 鉴权）"""

    name: str
    """模型名称"""
    base_url: str = "https://api.deepseek.com"
    """OpenAI 兼容 API 地址"""
    api_key: str | None = None
    """API Key"""
    api_type: ApiType | None = None
    """调用协议；缺省时 DeepSeek 官方支持的模型走 Responses，其余走 chat completions"""
    proxy: str | None = None
    """代理地址"""

    @property
    def is_deepseek_official(self) -> bool:
        return httpx.URL(self.base_url).host == DEEPSEEK_OFFICIAL_HOST

    @property
    def resolved_api_type(self) -> ApiType:
        if self.api_type:
            return self.api_type
        if self.is_deepseek_official and _deepseek_supports_responses(self.name):
            return "responses"
        return "chat"

    @property
    def resolved_base_url(self) -> str:
        """按协议解析实际请求地址（DeepSeek 官方的 Anthropic 端点在 /anthropic 下）"""
        if self.resolved_api_type != "anthropic" or not self.is_deepseek_official:
            return self.base_url
        url = httpx.URL(self.base_url)
        if url.path.rstrip("/").endswith(DEEPSEEK_ANTHROPIC_PATH):
            return self.base_url
        return str(url.copy_with(path=url.path.rstrip("/") + DEEPSEEK_ANTHROPIC_PATH))


class LLMProvider(BaseModel):
    """一个 OpenAI 兼容服务商（地址 + 鉴权），在 LLM__PROVIDERS 中注册"""

    base_url: str
    """OpenAI 兼容 API 地址"""
    api_key: str | None = None
    """API Key"""
    api_type: ApiType | None = None
    """调用协议；缺省时 DeepSeek 官方支持的模型走 Responses，其余走 chat completions"""
    proxy: str | None = None
    """代理地址"""


class LLMModel(BaseModel):
    """注册表中的一个模型（服务商引用 + 模型名），在 LLM__MODELS 中注册"""

    provider: str
    """服务商名称（LLM__PROVIDERS 中的键）"""
    name: str
    """模型名称"""
    api_type: ApiType | None = None
    """调用协议，覆写服务商级配置"""


def _parse_model_ref(ref: str) -> LLMModel:
    provider, sep, name = ref.partition(":")
    if not sep or not provider or not name:
        raise ValueError(f"模型引用 {ref!r} 应为 '服务商:模型名' 形式")
    return LLMModel(provider=provider, name=name)


class LLMScopedConfig(BaseModel):
    providers: dict[str, LLMProvider] = Field(default_factory=dict)
    """服务商注册表"""
    models: dict[str, LLMModel] = Field(default_factory=dict)
    """模型注册表；值支持 '服务商:模型名' 简写"""

    @field_validator("models", mode="before")
    @classmethod
    def _coerce_models(cls, value: object) -> object:
        if isinstance(value, dict):
            return {
                alias: _parse_model_ref(model) if isinstance(model, str) else model
                for alias, model in value.items()
            }
        return value


class _GlobalConfig(BaseModel):
    llm: LLMScopedConfig = Field(default_factory=LLMScopedConfig)
    """LLM 中央配置"""


@cache
def _llm_config() -> LLMScopedConfig:
    return get_plugin_config(_GlobalConfig).llm


def list_models() -> list[str]:
    """中央注册表中的全部模型别名"""
    return list(_llm_config().models)


def resolve_endpoint(ref: str) -> ModelEndpoint | None:
    """将模型引用解析为端点。

    ref 为 LLM__MODELS 中的别名，或 ``服务商:模型名`` 形式的直接引用。
    引用无效或服务商未配置 API Key 时返回 None 并记录警告。
    """
    config = _llm_config()
    model = config.models.get(ref)
    if model is None:
        if ":" not in ref:
            logger.warning(f"模型引用 {ref} 不在 LLM__MODELS 注册表中")
            return None
        model = _parse_model_ref(ref)

    provider = config.providers.get(model.provider)
    if provider is None:
        logger.warning(
            f"模型 {ref} 引用的服务商 {model.provider} 未在 LLM__PROVIDERS 中注册"
        )
        return None
    if not provider.api_key:
        logger.warning(f"服务商 {model.provider} 未配置 API Key")
        return None

    return ModelEndpoint(
        name=model.name,
        base_url=provider.base_url,
        api_key=provider.api_key,
        api_type=model.api_type or provider.api_type,
        proxy=provider.proxy,
    )


def require_endpoint(ref: str) -> ModelEndpoint:
    """同 resolve_endpoint，但解析失败时抛出 ValueError"""
    endpoint = resolve_endpoint(ref)
    if endpoint is None:
        raise ValueError(f"模型 {ref} 未正确配置，请检查 LLM__PROVIDERS / LLM__MODELS")
    return endpoint


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
