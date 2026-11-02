"""在群里管 QQ 官方机器人：按群停用、启用，登记本群的真实群号（仅超管）。

命令都由官方机器人处理（没开全量消息的群要 @ 它发），按它收到的 group_openid 和
自己的 AppID 记；超管也按官方机器人眼里的 member_openid 认，要写进 SUPERUSERS。

开关：QQ 号机器人和官方机器人在同一个群、官方机器人又开了群聊全量消息时，同一条
消息两边各处理一遍，命令回两次。两边的群 id 对不上，没法自动判断是不是同一个群，
所以由超管手动关：

- ``/官q 关``：官方机器人在本群不再处理任何消息（聊天记录照记），只认 ``/官q``
  和 @ 它的 ``/whoami``
- QQ 号机器人（Milky、OneBot）全部掉线时，关掉的群也照常处理，由官方机器人兜底

绑定：``/官q 绑定 <群号>`` 把本群的 group_openid 登记到这个群号下（见
:mod:`src.providers.group_binding`），OneBot 兼容接口往这个群号的推送就由官方机器人
发到本群。
"""

from typing import NoReturn

from nonebot import get_bots, logger, require
from nonebot.adapters import Bot, Event
from nonebot.adapters.milky import Bot as MilkyBot
from nonebot.adapters.onebot.v11 import Bot as OneBotBot
from nonebot.adapters.qq import GroupMessageCreateEvent
from nonebot.exception import IgnoredException
from nonebot.matcher import Matcher
from nonebot.message import run_preprocessor
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule

require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    CommandMeta,
    Option,
    Query,
    Subcommand,
    on_alconna,
)

from src.providers.group_binding import group_bindings

from .disabled import disabled_groups

__plugin_meta__ = PluginMetadata(
    "官方机器人管理",
    "按群停用、启用 QQ 官方机器人，登记本群的真实群号供推送使用（仅超管）",
    "/官q：查看本群官方机器人的状态和绑定的群号\n"
    "/官q 关、/官q 开：停用、启用\n"
    "/官q 绑定 <群号>：把本群登记为这个群号；/官q 绑定 -l：列出全部绑定\n"
    "/官q 解绑：去掉本群的群号",
)

EXEMPT_PLUGINS = frozenset({"chat_history", "whoami", "markdown_test"})
"""停用的群里照样交给它们：chat_history 只旁听不回话；whoami 只在被 @ 时回，
正是停用之后要拿来查 id 的；markdown_test 只在官方机器人上响应，不会和 QQ 号
机器人重复"""


def _client_online() -> bool:
    """有没有 QQ 号机器人在线：一个都没有时，停用的群也由官方机器人兜底"""
    return any(isinstance(bot, MilkyBot | OneBotBot) for bot in get_bots().values())


async def _official_group(event: Event) -> bool:
    return isinstance(event, GroupMessageCreateEvent)


official = on_alconna(
    Alconna(
        "官q",
        Subcommand("开", alias={"on"}, help_text="本群启用官方机器人"),
        Subcommand("关", alias={"off"}, help_text="本群停用官方机器人"),
        Subcommand(
            "绑定",
            Args["group_id?#真实群号", str],
            Option("-l|--list", dest="list", help_text="列出全部绑定"),
            alias={"bind"},
            help_text="把本群登记为这个群号，推送按群号找到本群",
        ),
        Subcommand("解绑", alias={"unbind"}, help_text="去掉本群的群号"),
        meta=CommandMeta(
            description="本群 QQ 官方机器人的开关与群号绑定",
            usage="/官q [开|关] | 绑定 <群号> | 绑定 -l | 解绑",
        ),
    ),
    aliases={"官Q"},
    rule=Rule(_official_group),
    permission=SUPERUSER,
    use_cmd_start=True,
)


async def _status(bot: Bot, event: GroupMessageCreateEvent) -> NoReturn:
    app_id, group_openid = bot.self_id, event.group_openid
    lines = (
        [
            "本群官方机器人：已停用，消息都交给 QQ 号机器人",
            "（QQ 号机器人全部掉线时自动兜底；/官q 开 重新启用）",
        ]
        if disabled_groups.disabled(app_id, group_openid)
        else ["本群官方机器人：启用中"]
    )
    group_id = group_bindings.find(app_id, group_openid)
    lines.append(
        f"绑定的群号：{group_id}" if group_id else "尚未绑定群号（/官q 绑定 <群号>）"
    )
    await official.finish("\n".join(lines))


@official.assign("开")
async def _(bot: Bot, event: GroupMessageCreateEvent) -> None:
    disabled_groups.enable(bot.self_id, event.group_openid)
    logger.info(f"官方机器人 {bot.self_id} 在群 {event.group_openid} 启用")
    await _status(bot, event)


@official.assign("关")
async def _(bot: Bot, event: GroupMessageCreateEvent) -> None:
    disabled_groups.disable(bot.self_id, event.group_openid, event.get_user_id())
    logger.info(f"官方机器人 {bot.self_id} 在群 {event.group_openid} 停用")
    await _status(bot, event)


@official.assign("绑定.list")
async def _() -> None:
    if not group_bindings.bindings:
        await official.finish("尚无群号绑定")
    await official.finish(
        "已绑定的群号：\n"
        + "\n".join(
            f"- {group_id} -> {binding.group_openid}"
            + (f"（AppID {binding.bot_id}）" if binding.bot_id else "")
            for group_id, binding in group_bindings.bindings.items()
        )
    )


@official.assign("绑定")
async def _(
    bot: Bot,
    event: GroupMessageCreateEvent,
    group_id: Query[str] = Query("绑定.group_id"),
) -> None:
    app_id, group_openid = bot.self_id, event.group_openid
    if not group_id.available:
        current = group_bindings.find(app_id, group_openid)
        await official.finish(
            (f"本群绑定的群号：{current}\n" if current else "本群尚未绑定群号\n")
            + "用法：/官q 绑定 <真实群号>"
        )
    if not group_id.result.isdigit():
        await official.finish(f"群号应为数字：{group_id.result}")

    previous = group_bindings.get(group_id.result)
    group_bindings.bind(group_id.result, app_id, group_openid)
    logger.info(f"官方机器人 {app_id} 的群 {group_openid} 绑定为群号 {group_id.result}")
    await official.finish(
        f"已把本群绑定为群号 {group_id.result}，往这个群号的推送改由官方机器人发到本群"
        + (
            f"\n（群号 {group_id.result} 原先绑定的另一个群已被覆盖）"
            if previous is not None and not previous.belongs_to(app_id, group_openid)
            else ""
        )
    )


@official.assign("解绑")
async def _(bot: Bot, event: GroupMessageCreateEvent) -> None:
    group_id = group_bindings.find(bot.self_id, event.group_openid)
    if group_id is None:
        await official.finish("本群尚未绑定群号")
    group_bindings.remove(group_id)
    logger.info(f"官方机器人 {bot.self_id} 的群 {event.group_openid} 解除绑定")
    await official.finish(f"已解除本群与群号 {group_id} 的绑定")


@official.handle()
async def _(bot: Bot, event: GroupMessageCreateEvent) -> None:
    await _status(bot, event)


@run_preprocessor
async def _(matcher: Matcher, bot: Bot, event: Event) -> None:
    if not isinstance(event, GroupMessageCreateEvent):
        return
    if isinstance(matcher, official) or matcher.plugin_id in EXEMPT_PLUGINS:
        return
    if disabled_groups.disabled(bot.self_id, event.group_openid) and _client_online():
        raise IgnoredException("本群已停用官方机器人")
