"""按群开关 QQ 官方机器人（仅超管）。

QQ 号机器人（Milky）和官方机器人在同一个群、官方机器人又开了群聊全量消息时，同一条
消息两边各处理一遍，命令回两次。官方机器人那边只有按 AppID 脱敏的 group_openid，
和群号对不上，没法可靠地自动判断两边是不是同一个群，所以由超管在群里手动关：

- ``/官q 关``：官方机器人在本群不再处理任何消息（聊天记录照记），只认 ``/官q``
  这条命令；没开全量消息的群要 @ 官方机器人发
- QQ 号机器人（Milky、OneBot）全部掉线时，关掉的群也照常处理，由官方机器人兜底

开关由官方机器人收到命令时按 group_openid 记下；超管也按官方机器人眼里的
member_openid 认，要写进 SUPERUSERS。
"""

from datetime import datetime
import json

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
from nonebot_plugin_alconna import Alconna, Args, CommandMeta, Match, on_alconna
from nonebot_plugin_localstore import get_plugin_data_file

__plugin_meta__ = PluginMetadata(
    "官方机器人开关",
    "和 QQ 号机器人同群时，按群停用 QQ 官方机器人，免得同一条命令回两次（仅超管）",
    "/官q：查看本群官方机器人是否启用\n/官q 关、/官q 开：停用、启用",
)

OBSERVERS = frozenset({"chat_history"})
"""只旁听、不回话的插件：停用的群里照样交给它们"""

ON, OFF = frozenset({"开", "on"}), frozenset({"关", "off"})


class DisabledGroups:
    """官方机器人 AppID -> 停用的 group_openid -> 谁、什么时候关的"""

    def __init__(self) -> None:
        self.file = get_plugin_data_file("disabled_groups.json")
        self.groups: dict[str, dict[str, dict[str, str]]] = {}
        if self.file.exists():
            try:
                self.groups = json.loads(self.file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.opt(exception=e).error(f"官方机器人开关读取失败：{self.file}")

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.groups, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self.file)

    def disabled(self, app_id: str, group_openid: str) -> bool:
        return group_openid in self.groups.get(app_id, {})

    def disable(self, app_id: str, group_openid: str, by: str) -> None:
        self.groups.setdefault(app_id, {})[group_openid] = {
            "by": by,
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        self.save()

    def enable(self, app_id: str, group_openid: str) -> None:
        groups = self.groups.get(app_id, {})
        if groups.pop(group_openid, None) is not None:
            if not groups:
                del self.groups[app_id]
            self.save()


disabled_groups = DisabledGroups()


def _client_online() -> bool:
    """有没有 QQ 号机器人在线：一个都没有时，停用的群也由官方机器人兜底"""
    return any(isinstance(bot, MilkyBot | OneBotBot) for bot in get_bots().values())


async def _official_group(event: Event) -> bool:
    return isinstance(event, GroupMessageCreateEvent)


switch = on_alconna(
    Alconna(
        "官q",
        Args["state?#开 或 关", str],
        meta=CommandMeta(
            description="按群停用、启用 QQ 官方机器人",
            usage="/官q [开|关]",
        ),
    ),
    aliases={"官Q"},
    rule=Rule(_official_group),
    permission=SUPERUSER,
    use_cmd_start=True,
)


@switch.handle()
async def _(bot: Bot, event: GroupMessageCreateEvent, state: Match[str]) -> None:
    app_id, group_openid = bot.self_id, event.group_openid
    if state.available:
        if state.result in OFF:
            disabled_groups.disable(app_id, group_openid, event.get_user_id())
            logger.info(f"官方机器人 {app_id} 在群 {group_openid} 停用")
        elif state.result in ON:
            disabled_groups.enable(app_id, group_openid)
            logger.info(f"官方机器人 {app_id} 在群 {group_openid} 启用")
        else:
            await switch.finish("用法：/官q [开|关]")

    if not disabled_groups.disabled(app_id, group_openid):
        await switch.finish("本群官方机器人：启用中")
    await switch.finish(
        "本群官方机器人：已停用，消息都交给 QQ 号机器人\n"
        "（QQ 号机器人全部掉线时自动兜底；/官q 开 重新启用）"
    )


@run_preprocessor
async def _(matcher: Matcher, bot: Bot, event: Event) -> None:
    if not isinstance(event, GroupMessageCreateEvent):
        return
    if isinstance(matcher, switch) or matcher.plugin_id in OBSERVERS:
        return
    if disabled_groups.disabled(bot.self_id, event.group_openid) and _client_online():
        raise IgnoredException("本群已停用官方机器人")
