from nonebot import get_plugin_config
from pydantic import BaseModel, Field

from src.libs.llm import ModelEndpoint, resolve_endpoint


class ScopedConfig(BaseModel):
    model: str = "deepseek:deepseek-v4-flash"
    """模型引用：LLM__MODELS 中的别名，或 '服务商:模型名'"""
    timeout: int = 60
    """API 请求超时（秒）"""
    temperature: float = Field(default=1.2, ge=0, le=2)
    """采样温度；调高可以让推荐更多样"""


class Config(BaseModel):
    what2eat: ScopedConfig = Field(default_factory=ScopedConfig)
    """What2Eat Plugin Config"""


w2e_config = get_plugin_config(Config).what2eat


def get_endpoint() -> ModelEndpoint | None:
    """获取推荐所用的模型端点，未正确配置时返回 None"""
    return resolve_endpoint(w2e_config.model)
