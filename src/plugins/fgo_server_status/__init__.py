from nonebot import require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_alconna")
require("nonebot_plugin_apscheduler")
require("nonebot_plugin_localstore")

from . import common as common
from . import manage as manage
from . import monitor as monitor
from .config import Config

__plugin_meta__ = PluginMetadata(
    "FGO 服务器状态查询",
    "定时推送及查询 FGO 服务器状态",
    "/服务器状态 国服|日服\n/维护推送 开启|关闭|列表 [群号]（仅超级用户）",
    config=Config,
)
