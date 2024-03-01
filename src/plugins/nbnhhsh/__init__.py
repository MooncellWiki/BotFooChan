from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from .config import Config

config = get_plugin_config(Config)

__plugin_meta__ = PluginMetadata(
    name="能不能好好说话",
    description="提供拼音首字母缩写查询",
    usage="/hhsh, /nbnhhsh, /好好说话, /人话 [缩写]：查询拼音首字母缩写",
    config=Config,
)

from . import common as common
