from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict, Field

from src.providers.settings import register


class ScopedConfig(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    size: int = Field(default=200, gt=0, json_schema_extra={"restart": True})
    """每个会话在内存里保留的消息条数，也是模型用工具最多能往前翻到的范围"""
    max_text_length: int = Field(default=300, gt=0)
    """单条消息进提示词时的截断长度（字符）"""


class Config(BaseModel):
    chat_history: ScopedConfig = Field(default_factory=ScopedConfig)
    """Chat History Provider Config"""


history_config = register(
    "chat_history",
    ScopedConfig,
    title="会话消息缓冲",
    description="各插件共用的最近消息缓冲",
    env=lambda: get_plugin_config(Config).chat_history,
)
