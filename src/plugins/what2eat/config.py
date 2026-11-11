from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict, Field

from src.providers.llm import ModelEndpoint, resolve_endpoint
from src.providers.settings import register


class ScopedConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    model: str = Field(
        default="deepseek:deepseek-v4-flash", json_schema_extra={"model_ref": True}
    )
    """模型引用：模型注册表里的别名，或 '服务商:模型名'"""
    timeout: int = 60
    """API 请求超时（秒）"""
    temperature: float = Field(default=1.2, ge=0, le=2)
    """采样温度；调高可以让推荐更多样"""
    history_rounds: int = Field(default=10, ge=0, json_schema_extra={"restart": True})
    """每个会话记住最近多少次推荐，用于避免短期内重复；置 0 关闭去重"""
    min_suggestions: int = Field(default=1, ge=1)
    """单次推荐至少给几样"""
    max_suggestions: int = Field(default=5, ge=1)
    """单次推荐最多给几样"""


class Config(BaseModel):
    what2eat: ScopedConfig = Field(default_factory=ScopedConfig)
    """What2Eat Plugin Config"""


w2e_config = register(
    "what2eat",
    ScopedConfig,
    title="今天吃什么",
    description="让 AI 推荐吃什么、喝什么",
    env=lambda: get_plugin_config(Config).what2eat,
)


def get_endpoint() -> ModelEndpoint | None:
    """获取推荐所用的模型端点，未正确配置时返回 None"""
    return resolve_endpoint(w2e_config.model)
