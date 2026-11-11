"""用户记忆的压缩策略配置"""

from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.providers.settings import register


class ScopedConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    model: str | None = Field(default=None, json_schema_extra={"model_ref": True})
    """压缩档案用的模型（模型注册表里的别名）；未配置时退化为按行截断"""
    max_chars: int = Field(default=1500, gt=0)
    """档案超过这个长度（字符）就触发压缩"""
    target_chars: int = Field(default=900, gt=0)
    """压缩后的目标长度（字符）"""
    timeout: int = Field(default=60, gt=0)
    """压缩请求的超时（秒）"""

    @model_validator(mode="after")
    def _check_target(self) -> "ScopedConfig":
        if self.target_chars >= self.max_chars:
            raise ValueError("user_memory.target_chars 必须小于 max_chars")
        return self


class Config(BaseModel):
    user_memory: ScopedConfig = Field(default_factory=ScopedConfig)
    """User Memory Provider Config"""


memory_config = register(
    "user_memory",
    ScopedConfig,
    title="群友记忆",
    description="按人建档的长期记忆，档案过长时用模型压缩",
    env=lambda: get_plugin_config(Config).user_memory,
)
