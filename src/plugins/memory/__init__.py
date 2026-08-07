from nonebot.plugin import PluginMetadata

from . import common as common

__plugin_meta__ = PluginMetadata(
    "群友记忆",
    "记录群友的喜好与地区，供个性化推荐使用",
    "发送“记住 <内容>”记录喜好或忌口，“设置地区 <地区>”设置所在地区，"
    "“我的记忆”查看已记录的内容，“忘记 <关键词>”删除匹配的记录，"
    "“清空记忆”清空全部记录",
)
