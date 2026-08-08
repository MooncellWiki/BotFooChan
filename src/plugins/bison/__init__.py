from nonebot import require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_alconna")
require("nonebot_plugin_apscheduler")
require("nonebot_plugin_htmlrender")
require("nonebot_plugin_localstore")
# 必须先 require，orm 的 startup 钩子要排在 bootstrap 之前
require("nonebot_plugin_orm")

from nonebot_plugin_alconna import __plugin_meta__ as _alconna_meta

from . import bootstrap as bootstrap
from . import config as config
from . import platform as platform
from . import post as post
from . import scheduler as scheduler
from . import send as send
from . import sub_manager as sub_manager
from . import theme as theme
from . import types as types
from . import utils as utils
from .plugin_config import PlugConfig, plugin_config

__usage__ = (
    "本bot可以提供b站、微博等社交媒体的消息订阅，"
    f"{'at本bot' if plugin_config.bison_to_me else ''}发送“添加订阅”订阅第一个帐号，"
    "发送“查询订阅”或“删除订阅”管理订阅"
)

__plugin_meta__ = PluginMetadata(
    name="Bison",
    description="通用订阅推送插件",
    usage=__usage__,
    type="application",
    homepage="https://github.com/MountainDash/nonebot-bison",
    config=PlugConfig,
    supported_adapters=_alconna_meta.supported_adapters,
)
