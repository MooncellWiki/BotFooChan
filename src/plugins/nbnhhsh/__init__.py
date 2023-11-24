from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from .config import Config

config = Config.parse_obj(get_driver().config)

__plugin_meta__ = PluginMetadata(
    "能不能好好说话",
    "提供拼音首字母缩写查询",
    "/hhsh, /nbnhhsh, /好好说话, /人话 [缩写]：查询拼音首字母缩写",
)

from . import common as common
