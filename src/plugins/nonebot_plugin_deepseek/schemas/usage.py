from typing import Optional
from dataclasses import dataclass


@dataclass
class PromptTokensDetails:
    cached_tokens: Optional[int] = None


@dataclass
class CompletionTokensDetails:
    """completion tokens 的详细信息。"""

    reasoning_tokens: Optional[int] = None
    """推理模型所产生的思维链 token 数量"""


@dataclass
class Usage:
    """该对话补全请求的用量信息"""

    completion_tokens: int
    """模型 completion 产生的 token 数"""
    prompt_tokens: int
    """
    用户 prompt 所包含的 token 数
    该值等于 `prompt_cache_hit_token`s + `prompt_cache_miss_tokens`
    """
    total_tokens: int
    """该请求中，所有 token 的数量（prompt + completion）"""
    prompt_tokens_details: Optional[PromptTokensDetails] = None
    """我也不知道这是个啥，文档没写"""
    prompt_cache_hit_tokens: Optional[int] = None
    """用户 prompt 中，命中上下文缓存的 token 数"""
    prompt_cache_miss_tokens: Optional[int] = None
    """用户 prompt 中，未命中上下文缓存的 token 数"""
    completion_tokens_details: Optional[CompletionTokensDetails] = None

    def __post_init__(self) -> None:
        if isinstance(self.prompt_tokens_details, dict):
            self.prompt_tokens_details = PromptTokensDetails(**self.prompt_tokens_details)
        if isinstance(self.completion_tokens_details, dict):
            self.completion_tokens_details = CompletionTokensDetails(**self.completion_tokens_details)
