"""基于 pydantic-ai 的统一 LLM 调用封装。

项目内插件的模型调用统一通过本模块创建 Agent：

- DeepSeek 官方 API 默认走 OpenAI Responses API 兼容协议
- 其他 OpenAI 兼容服务（硅基流动、OpenRouter 等）走 chat completions 协议

服务商与模型统一在全局配置中注册，各插件只持有一个模型引用：

- ``LLM__PROVIDERS``：服务商注册表，``名称 -> {base_url, api_key, ...}``，Key 只配置一次
- ``LLM__MODELS``：模型注册表，``别名 -> "服务商:模型名"``（或对象形式以覆写协议等字段）

插件配置中的模型引用既可以是注册表别名，也可以直接写 ``服务商:模型名``。
"""

from collections.abc import Sequence
from functools import cache
import re
from typing import Literal

import httpx
from nonebot import get_plugin_config, logger
from pydantic import BaseModel, Field, field_validator
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.capabilities import NativeTool
from pydantic_ai.messages import ModelMessage, ModelResponse, ThinkingPart
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from pydantic_ai.native_tools import WebSearchTool
from pydantic_ai.output import OutputSpec
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

DEEPSEEK_OFFICIAL_HOST = "api.deepseek.com"

ApiType = Literal["responses", "chat"]


class ModelEndpoint(BaseModel):
    """描述一个可调用的模型端点（模型名 + 服务地址 + 鉴权）"""

    name: str
    """模型名称"""
    base_url: str = "https://api.deepseek.com"
    """OpenAI 兼容 API 地址"""
    api_key: str | None = None
    """API Key"""
    api_type: ApiType | None = None
    """调用协议；缺省时 DeepSeek 官方走 Responses API，其余走 chat completions"""
    proxy: str | None = None
    """代理地址"""

    @property
    def is_deepseek_official(self) -> bool:
        return httpx.URL(self.base_url).host == DEEPSEEK_OFFICIAL_HOST

    @property
    def resolved_api_type(self) -> ApiType:
        if self.api_type:
            return self.api_type
        return "responses" if self.is_deepseek_official else "chat"


class LLMProvider(BaseModel):
    """一个 OpenAI 兼容服务商（地址 + 鉴权），在 LLM__PROVIDERS 中注册"""

    base_url: str
    """OpenAI 兼容 API 地址"""
    api_key: str | None = None
    """API Key"""
    api_type: ApiType | None = None
    """调用协议；缺省时 DeepSeek 官方走 Responses API，其余走 chat completions"""
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
    if endpoint.is_deepseek_official:
        provider = DeepSeekProvider(api_key=endpoint.api_key, http_client=http_client)
    else:
        provider = OpenAIProvider(
            base_url=endpoint.base_url,
            api_key=endpoint.api_key,
            http_client=http_client,
        )

    model_cls = (
        OpenAIResponsesModel
        if endpoint.resolved_api_type == "responses"
        else OpenAIChatModel
    )
    model = model_cls(endpoint.name, provider=provider)
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

    web_search 启用服务商内置的联网搜索（服务端执行），仅 Responses API 协议支持；
    DeepSeek 官方对应 tools=[{"type": "web_search"}]。
    """
    capabilities = None
    if web_search:
        if endpoint.resolved_api_type == "responses":
            capabilities = [NativeTool(WebSearchTool())]
        else:
            logger.warning(
                f"模型 {endpoint.name} 走 chat completions 协议，"
                "不支持内置联网搜索，已忽略"
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


def extract_thinking(messages: Sequence[ModelMessage]) -> str:
    """收集模型响应中的思维链内容"""
    chunks = [
        part.content
        for message in messages
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, ThinkingPart) and part.content
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
