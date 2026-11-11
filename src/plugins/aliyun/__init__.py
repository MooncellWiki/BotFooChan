from pathlib import Path

import nonebot
from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata

from src.providers.settings import register

from .config import Config

__plugin_meta__ = PluginMetadata(
    "阿里云",
    "阿里云开放功能插件",
    "见子插件使用方法",
)

config = register(
    "aliyun",
    Config,
    title="阿里云",
    description="CDN 状态与带宽查询",
    env=lambda: get_plugin_config(Config),
)

# load all aliyun subplugins
_sub_plugins = set()
_sub_plugins |= nonebot.load_plugins(str((Path(__file__).parent / "plugins").resolve()))
