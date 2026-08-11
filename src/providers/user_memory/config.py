"""用户记忆的压缩策略配置"""

from nonebot import get_plugin_config
from pydantic import BaseModel, Field, model_validator


class ScopedConfig(BaseModel):
    model: str | None = None
    """压缩档案用的模型（LLM__MODELS 中的别名）；未配置时退化为按行截断"""
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


memory_config = get_plugin_config(Config).user_memory
