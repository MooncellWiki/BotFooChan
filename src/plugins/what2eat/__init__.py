from nonebot.plugin import PluginMetadata

from . import common as common

__plugin_meta__ = PluginMetadata(
    "今天吃/喝什么",
    "提供今天吃/喝什么的建议",
    "发送“(今天|[早中午晚][上饭餐午]|早上|夜宵|今晚)吃(什么|啥|点啥)”"
    "或者“(今天|[早中午晚][上饭餐午]|早上|夜宵|今晚)喝(什么|啥|点啥)”"
    "即可获得建议",
)
