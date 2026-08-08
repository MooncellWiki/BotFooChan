"""LLM 中央配置：服务商与模型注册表。

- ``LLM__PROVIDERS``：服务商注册表，``名称 -> {base_url, api_key, ...}``，Key 只配置一次
- ``LLM__MODELS``：模型注册表，``别名 -> "服务商:模型名"``（或对象形式以覆写协议等字段）

插件配置中的模型引用既可以是注册表别名，也可以直接写 ``服务商:模型名``。
"""

from typing import Literal

import httpx
from nonebot import get_plugin_config, logger
from pydantic import BaseModel, Field, field_validator

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


class ScopedConfig(BaseModel):
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


class Config(BaseModel):
    llm: ScopedConfig = Field(default_factory=ScopedConfig)
    """LLM Provider Config"""


llm_config = get_plugin_config(Config).llm


def list_models() -> list[str]:
    """中央注册表中的全部模型别名"""
    return list(llm_config.models)


def resolve_endpoint(ref: str) -> ModelEndpoint | None:
    """将模型引用解析为端点。

    ref 为 LLM__MODELS 中的别名，或 ``服务商:模型名`` 形式的直接引用。
    引用无效或服务商未配置 API Key 时返回 None 并记录警告。
    """
    model = llm_config.models.get(ref)
    if model is None:
        if ":" not in ref:
            logger.warning(f"模型引用 {ref} 不在 LLM__MODELS 注册表中")
            return None
        model = _parse_model_ref(ref)

    provider = llm_config.providers.get(model.provider)
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
