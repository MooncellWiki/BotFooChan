from pathlib import Path

import nonebot
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    "阿里云",
    "阿里云开放功能插件",
    "见子插件使用方法",
)

# load all aliyun plugin config from global config
config = Config.parse_obj(nonebot.get_driver().config)

# load all aliyun subplugins
_sub_plugins = set()
_sub_plugins |= nonebot.load_plugins(str((Path(__file__).parent / "plugins").resolve()))
