"""判断一条消息是不是明确 @ 了某个机器人。

``to_me`` 比「被 @」宽得多：消息以 NICKNAME 开头、回复了机器人的消息都算。要的是
真被 @ 了的场合（通用对话接话、/whoami），就得自己从消息里找那个 @。
"""

from nonebot import require
from nonebot.adapters import Bot, Event

require("nonebot_plugin_alconna")
from nonebot_plugin_alconna.uniseg import At, UniMessage

_ID_ATTRS = ("user_id", "id", "open_id", "union_id", "user_openid", "tiny_id")


def ids_of(owner: object) -> set[str]:
    """从「某个人」的模型对象里把 id 抠出来。

    各适配器的字段名不统一（QQ、Discord 是 ``id``，飞书是 ``open_id``），认不出来的
    就当没有，多收一个 id 也只是多挡一次。
    """
    return {str(value) for attr in _ID_ATTRS if (value := getattr(owner, attr, None))}


def bot_ids(bot: Bot) -> set[str]:
    """一个账号在别人眼里可能是什么 id。

    ``self_id`` 未必就是群里露出来的那个：官方 QQ 的是 AppID、发言时用的是
    ``self_info.id``，Discord 的是 application id、@ 它时用的是 ``self_info.id``，
    飞书则要看 ``bot_info.open_id``。
    """
    ids = {str(bot.self_id)}
    for attr in ("self_info", "bot_info"):
        try:
            owner = getattr(bot, attr, None)
        except Exception:  # QQ 的 self_info 在连接就绪前会抛
            continue
        ids |= ids_of(owner)
    return ids


def at_targets(bot: Bot, event: Event, msg: UniMessage) -> set[str]:
    """这条消息 @ 了谁。

    不能只看 msg：适配器判定 to_me 时，做的正是把开头/结尾那个「@机器人」从消息
    里删掉。QQ、飞书、Discord 都把原文留在 ``original_message`` 里（QQ 群 @ 事件会
    补回一个 @ 自己），飞书另外还有一份 mentions，两处都翻一遍。

    QQ 群消息的 ``original_message`` 也不全：回复别人时客户端自动带上的那个 @，
    适配器在认「回复的是谁」时就删了，之后才存原文。好在事件上还有原样的
    mentions，@ 到自己的那条带 ``is_you``（给的 id 不是 ``self_info.id``，对不上号）。
    """
    if (raw := getattr(event, "original_message", None)) is not None:
        try:
            msg = UniMessage.of(raw, bot=bot)
        except Exception:
            pass

    targets = {seg.target for seg in msg if isinstance(seg, At)}
    message = getattr(getattr(event, "event", None), "message", None)
    for mention in getattr(message, "mentions", None) or []:
        targets |= ids_of(getattr(mention, "id", None))
    # @全体成员 的 is_you 恒为真，不算
    for mention in getattr(event, "mentions", None) or []:
        if getattr(mention, "scope", None) == "single" and getattr(
            mention, "is_you", False
        ):
            targets |= bot_ids(bot)
    return targets


def mentions_bot(bot: Bot, event: Event, msg: UniMessage) -> bool:
    """消息里明确 @ 了 ``bot`` 自己"""
    return bool(at_targets(bot, event, msg) & bot_ids(bot))
