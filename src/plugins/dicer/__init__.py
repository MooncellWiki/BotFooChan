from nonebot.plugin import PluginMetadata

from . import common as common
from .constant import main as main_help

__plugin_meta__ = PluginMetadata(
    "COC骰娘",
    "提供骰子支持",
    main_help,
)
