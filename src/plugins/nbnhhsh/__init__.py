import nonebot
from nonebot.plugin import PluginMetadata

from .config import Config
from . import common as common

nbnhhsh_config = Config.parse_obj(nonebot.get_driver().config)

__plugin_meta__ = PluginMetadata(
    "能不能好好说话",
    "提供拼音首字母缩写查询",
    "/hhsh, /nbnhhsh, /好好说话, /人话 [缩写]：查询拼音首字母缩写",
)
