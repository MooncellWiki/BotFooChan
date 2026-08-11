from nonebot.plugin import PluginMetadata

from . import common as common

__plugin_meta__ = PluginMetadata(
    "群友记忆",
    "查看与管理我记住的关于你的事",
    "记忆由聊天时自动积累（@ 我聊天即可），这里只负责查看与修改：\n"
    "“我的记忆”查看已记录的内容，“编辑记忆”整份改写，“清空记忆”清空全部记录",
)
