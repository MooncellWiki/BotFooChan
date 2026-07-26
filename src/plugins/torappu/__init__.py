from nonebot import require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_alconna")

from . import common as common
from . import manage as manage
from .config import Config

__plugin_meta__ = PluginMetadata(
    "Torappu 资源站",
    "查询 torappu 资源站的版本、资源与需求数据，并支持发起资源重跑",
    "/torappu状态：查询服务状态\n"
    "/torappu版本 [版本]：查询版本列表或版本详情\n"
    "/torappu搜索 <关键词> [版本]：搜索资源清单\n"
    "/torappu详情 <资源路径> [版本]：查询资源所属 bundle\n"
    "/torappu目录 [路径] [版本]：浏览资源清单目录\n"
    "/torappu文件 <关键词|目录路径/>：搜索或列出解包文件\n"
    "/torappu包 <bundle路径|ID> [版本]：查询 bundle 版本记录\n"
    "/材料需求 <道具名>：查询干员对道具的需求统计\n"
    "/重跑 [版本] [上一版本] [--include 路径] [--exclude 路径]（仅超级用户）\n"
    "版本参数可为版本 ID 或 res 版本号，缺省时使用最新版本",
    config=Config,
)
