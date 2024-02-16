from nonebot.plugin import PluginMetadata

from . import common as common

__plugin_meta__ = PluginMetadata(
    "哔哩哔哩解析",
    "解析哔哩哔哩视频并发送短链接及小程序链接等信息",
    (
        r"av(\d{1,12})|BV(1[A-Za-z0-9]{2}4.1.7[A-Za-z0-9]{2})"
        "：解析哔哩哔哩视频 AV/BV 号\n"
        "/bvideo av/BV123456：解析哔哩哔哩视频 av/BV123456\n"
    ),
)
