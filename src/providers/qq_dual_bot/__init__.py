"""QQ 号机器人（Milky、OneBot）和 QQ 官方机器人在同一个群里时的分工。

官方机器人开了群聊全量消息（``GROUP_MESSAGE_CREATE``）以后，同一条消息两边都会
收到、各跑一遍命令，回两次；两边还会把对方的回复当成群友的话接着处理。

要去重得先知道「这是同一个群」，可官方机器人那边只有按 AppID 脱敏的 group_openid、
member_openid，没有哪个算法能从群号、QQ 号推出来。这里靠观察来认：一个机器人在群里
回了一句，另一个机器人几秒内收到一字不差的原话，两边就对上了（见 :mod:`.store`）。
认出来之后：

- 没有 @ 官方机器人的消息归 QQ 号机器人管，官方机器人这边只记聊天记录；QQ 号机器人
  掉线时官方机器人照常处理，算是备份
- @ 了官方机器人的消息（``GROUP_AT_MESSAGE_CREATE``）归官方机器人，QQ 号机器人
  不管
- 对方机器人发的消息，两边都不处理

刚进同一个群时还没认出来，头一两条命令仍会回两次，随后的回复一对上就好了。
"""

from nonebot import get_bots, logger, require
from nonebot.adapters import Bot, Event
from nonebot.adapters.milky import Bot as MilkyBot
from nonebot.adapters.milky import Message as MilkyMessage
from nonebot.adapters.milky.event import GroupDisbandEvent, GroupMemberDecreaseEvent
from nonebot.adapters.milky.event import GroupMessageEvent as MilkyGroupMessageEvent
from nonebot.adapters.onebot.v11 import Bot as OneBotBot
from nonebot.adapters.onebot.v11 import GroupDecreaseNoticeEvent
from nonebot.adapters.onebot.v11 import GroupMessageEvent as OneBotGroupMessageEvent
from nonebot.adapters.onebot.v11 import Message as OneBotMessage
from nonebot.adapters.qq import Bot as QQBot
from nonebot.adapters.qq import GroupAtMessageCreateEvent, GroupMessageCreateEvent
from nonebot.adapters.qq.event import GroupDelRobotEvent
from nonebot.exception import IgnoredException
from nonebot.matcher import Matcher, current_event
from nonebot.message import event_preprocessor, run_preprocessor

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file

from .store import OfficialAccount as OfficialAccount
from .store import SharedGroup as SharedGroup
from .store import SharedGroupStore

shared_groups = SharedGroupStore(get_plugin_data_file("shared_groups.json"))

OBSERVERS = frozenset({"chat_history"})
"""只旁听、不回话的插件：被分给另一边的消息照样交给它们"""

ClientGroupMessageEvent = MilkyGroupMessageEvent | OneBotGroupMessageEvent


def _online(bot_id: str, kind: type[Bot] | tuple[type[Bot], ...]) -> bool:
    return isinstance(get_bots().get(bot_id), kind)


# region 认人


@Bot.on_calling_api
async def _record_sent(bot: Bot, api: str, data: dict) -> None:
    # 只认回复：处理某条消息的过程中发出去的（定时推送没有当前事件）
    if current_event.get(None) is None:
        return
    try:
        if isinstance(bot, MilkyBot) and api == "send_group_message":
            text = MilkyMessage(data["message"]).extract_plain_text()
            shared_groups.record_sent(
                "client", bot.self_id, str(data["group_id"]), text
            )
        elif isinstance(bot, OneBotBot) and (
            api == "send_group_msg"
            or (api == "send_msg" and data.get("message_type") != "private")
        ):
            if (group_id := data.get("group_id")) is not None:
                text = OneBotMessage(data["message"]).extract_plain_text()
                shared_groups.record_sent("client", bot.self_id, str(group_id), text)
        elif isinstance(bot, QQBot) and api == "post_group_messages":
            if content := data.get("content"):
                shared_groups.record_sent(
                    "official", bot.self_id, data["group_openid"], content
                )
    except Exception as e:
        logger.opt(exception=e).debug("记录发出的消息失败")


@event_preprocessor
async def _observe(bot: Bot, event: Event) -> None:
    try:
        if isinstance(event, GroupMessageCreateEvent):
            shared_groups.observe_official(
                bot.self_id,
                event.group_openid,
                event.author.member_openid,
                event.get_message().extract_plain_text(),
            )
        elif isinstance(event, MilkyGroupMessageEvent):
            shared_groups.observe_client(
                bot.self_id,
                event.data.peer_id,
                str(event.data.sender_id),
                event.data.message.extract_plain_text(),
            )
        elif isinstance(event, OneBotGroupMessageEvent):
            shared_groups.observe_client(
                bot.self_id,
                event.group_id,
                str(event.user_id),
                event.original_message.extract_plain_text(),
            )
        elif isinstance(event, GroupMemberDecreaseEvent):
            if str(event.data.user_id) == bot.self_id:
                shared_groups.forget_client_group(bot.self_id, event.data.group_id)
        elif isinstance(event, GroupDisbandEvent):
            shared_groups.forget_client_group(bot.self_id, event.data.group_id)
        elif isinstance(event, GroupDecreaseNoticeEvent):
            if event.is_tome():
                shared_groups.forget_client_group(bot.self_id, event.group_id)
        elif isinstance(event, GroupDelRobotEvent):
            shared_groups.forget_official_group(event.group_openid)
    except Exception as e:
        # 认人失败不能拖累正常处理
        logger.opt(exception=e).debug("同群关系识别失败")


# region 分工


def _mentioned(event: ClientGroupMessageEvent) -> set[str]:
    if isinstance(event, MilkyGroupMessageEvent):
        message, kind, key = event.data.message, "mention", "user_id"
    else:
        message, kind, key = event.original_message, "at", "qq"
    return {str(seg.data[key]) for seg in message if seg.type == kind}


def _official_to_handle(event: ClientGroupMessageEvent) -> OfficialAccount | None:
    """消息 @ 的是在线的官方机器人（且没有 @ 我们），交给它"""
    if event.is_tome():
        return None
    for uin in _mentioned(event):
        account = shared_groups.official(uin)
        if account is not None and _online(account.app_id, QQBot):
            return account
    return None


def skip_reason(event: Event) -> str | None:
    """这条消息该由另一边的机器人处理时，说明原因"""
    if isinstance(event, GroupMessageCreateEvent):
        if (group := shared_groups.shared(event.group_openid)) is None:
            return None
        if event.author.member_openid == group.member_openid:
            return f"QQ 号机器人 {group.client_id} 自己发的"
        if not isinstance(event, GroupAtMessageCreateEvent) and _online(
            group.client_id, (MilkyBot, OneBotBot)
        ):
            return f"群 {group.group_id} 里有 QQ 号机器人 {group.client_id}，由它处理"
    elif isinstance(event, ClientGroupMessageEvent):
        sender = str(
            event.data.sender_id
            if isinstance(event, MilkyGroupMessageEvent)
            else event.user_id
        )
        if (account := shared_groups.official(sender)) is not None:
            return f"官方机器人 {account.app_id} 发的"
        if (account := _official_to_handle(event)) is not None:
            return f"@ 的是官方机器人 {account.app_id}，由它处理"
    return None


@run_preprocessor
async def _route(matcher: Matcher, event: Event) -> None:
    if matcher.plugin_id in OBSERVERS:
        return
    try:
        reason = skip_reason(event)
    except Exception as e:
        logger.opt(exception=e).debug("同群分工判断失败，照常处理")
        return
    if reason is not None:
        raise IgnoredException(reason)
