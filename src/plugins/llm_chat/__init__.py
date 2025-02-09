from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

config = get_plugin_config(Config)

__plugin_meta__ = PluginMetadata(
    name="LLM 对话插件", description="进行 LLM 对话", usage="/ds [内容]", config=Config
)

from . import common as common
