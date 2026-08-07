"""基于 pydantic-ai 的统一 LLM 调用封装。

项目内插件的模型调用统一通过本模块创建 Agent：

- DeepSeek 官方 API 默认走 OpenAI Responses API 兼容协议
- 其他 OpenAI 兼容服务（硅基流动、OpenRouter 等）走 chat completions 协议
"""

from collections.abc import Sequence
import re
from typing import Literal

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.messages import ModelMessage, ModelResponse, ThinkingPart
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
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
) -> Agent[None, OutputT]:
    """按端点创建 pydantic-ai Agent"""
    return Agent(
        get_model(endpoint),
        instructions=instructions,
        output_type=output_type,
        model_settings=settings,
        retries=retries,
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
