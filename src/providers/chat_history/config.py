from nonebot import get_plugin_config
from pydantic import BaseModel, Field


class ScopedConfig(BaseModel):
    size: int = Field(default=200, gt=0)
    """每个会话在内存里保留的消息条数，也是模型用工具最多能往前翻到的范围"""
    max_text_length: int = Field(default=300, gt=0)
    """单条消息进提示词时的截断长度（字符）"""


class Config(BaseModel):
    chat_history: ScopedConfig = Field(default_factory=ScopedConfig)
    """Chat History Provider Config"""


history_config = get_plugin_config(Config).chat_history
