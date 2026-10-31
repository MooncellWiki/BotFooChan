"""服务器状态：``/status``、``/状态``，QQ 客户端（OneBot、Milky）下还能戳一戳机器人。

接的是 QQ-GitHub-Bot 的 multi_status：原版借 Redis 的发布订阅把多个实例的状态
攒到一起，这里只有一个进程，直接渲染 nonebot-plugin-status 的模板就够了。

插件自带的命令不认命令前缀，而本项目的 COMMAND_START 含空串，「状态不错」这种话
也会被当成命令，所以 .env 里把它自带的 matcher 关掉（SERVER_STATUS_ENABLED=false），
在这里注册一份要求带 / 的；戳一戳本来就不是文字命令，照原样保留。
"""

from nonebot import on_command, on_message, on_type, require
from nonebot.adapters.milky.event import FriendNudgeEvent, GroupNudgeEvent
from nonebot.adapters.onebot.v11 import PokeNotifyEvent, PrivateMessageEvent
from nonebot.matcher import Matcher
from nonebot.params import CommandStart
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule, to_me

require("nonebot_plugin_status")
from nonebot_plugin_status import render_template, status_config, status_permission

__plugin_meta__ = PluginMetadata(
    "Bot 运行状态",
    "查看机器人自身的运行时长、CPU 与内存占用（FGO 的是 /服务器状态）",
    "/status, /状态: 查看服务器状态\nQQ 私聊戳一戳或群里拍一拍机器人: 同上",
)


async def server_status(matcher: Matcher) -> None:
    await matcher.finish(await render_template())


async def _prefixed(command_start: str = CommandStart()) -> bool:
    return bool(command_start)


async def _private_poke(event: PrivateMessageEvent) -> bool:
    return (
        event.sub_type == "friend"
        and bool(event.message)
        and event.message[0].type == "poke"
    )


# 插件自带的那套还开着时就别再注册一遍，否则同一条命令会回两次
if not status_config.server_status_enabled:
    on_command(
        "status",
        aliases={"状态"},
        rule=Rule(_prefixed),
        permission=status_permission,
        priority=10,
        block=True,
        handlers=[server_status],
    )
    on_type(
        (PokeNotifyEvent, FriendNudgeEvent, GroupNudgeEvent),
        rule=to_me(),
        permission=status_permission,
        priority=10,
        block=True,
        handlers=[server_status],
    )
    on_message(
        Rule(_private_poke),
        permission=status_permission,
        priority=10,
        block=True,
        handlers=[server_status],
    )
