"""在群里登记 QQ 官方机器人所在群的真实群号（仅超管）。

命令都由官方机器人处理（没开全量消息的群要 @ 它发），按它收到的 group_openid 和
自己的 AppID 记；超管也按官方机器人眼里的 member_openid 认，要写进 SUPERUSERS。

``/官q 绑定 <群号>`` 把本群的 group_openid 登记到这个群号下（见
:mod:`src.providers.group_binding`），OneBot 兼容接口往这个群号的推送就由官方机器人
发到本群，bison 和 GitHub 订阅、FGO 维护推送在这个群号上的推送也一并转给官方机器人。
"""

from typing import NoReturn

from nonebot import logger, require
from nonebot.adapters import Bot, Event
from nonebot.adapters.qq import GroupMessageCreateEvent
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule

require("nonebot_plugin_alconna")
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

__plugin_meta__ = PluginMetadata(
    "官方机器人管理",
    "登记 QQ 官方机器人所在群的真实群号供推送使用（仅超管）",
    "/官q：查看本群绑定的群号\n"
    "/官q 绑定 <群号>：把本群登记为这个群号；/官q 绑定 -l：列出全部绑定\n"
    "/官q 解绑：去掉本群的群号",
)


async def _official_group(event: Event) -> bool:
    return isinstance(event, GroupMessageCreateEvent)


official = on_alconna(
    Alconna(
        "官q",
        Subcommand(
            "绑定",
            Args["group_id?#真实群号", str],
            Option("-l|--list", dest="list", help_text="列出全部绑定"),
            alias={"bind"},
            help_text="把本群登记为这个群号，推送按群号找到本群",
        ),
        Subcommand("解绑", alias={"unbind"}, help_text="去掉本群的群号"),
        meta=CommandMeta(
            description="本群 QQ 官方机器人的群号绑定",
            usage="/官q | 绑定 <群号> | 绑定 -l | 解绑",
        ),
    ),
    aliases={"官Q"},
    rule=Rule(_official_group),
    permission=SUPERUSER,
    use_cmd_start=True,
)


async def _status(bot: Bot, event: GroupMessageCreateEvent) -> NoReturn:
    if group_id := group_bindings.find(bot.self_id, event.group_openid):
        await official.finish(f"本群绑定的群号：{group_id}")
    await official.finish("本群尚未绑定群号（/官q 绑定 <群号>）")


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
    notes = await group_bindings.bind(group_id.result, app_id, group_openid)
    logger.info(f"官方机器人 {app_id} 的群 {group_openid} 绑定为群号 {group_id.result}")
    lines = [
        f"已把本群绑定为群号 {group_id.result}，往这个群号的推送改由官方机器人发到本群"
    ]
    if previous is not None and not previous.belongs_to(app_id, group_openid):
        lines.append(f"（群号 {group_id.result} 原先绑定的另一个群已被覆盖）")
    await official.finish("\n".join(lines + notes))


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
