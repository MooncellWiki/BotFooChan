"""判断一条消息是不是真的在叫我们。

原来用的 ``to_me()`` 比「被 @ 或被回复」宽得多，三个适配器都还额外认两件事：

- **消息以 NICKNAME 开头**：群里另一个机器人的回答里带上「芙芙」两个字，
  我们这边就被叫醒了
- **回复了机器人发过的那条**：这是它判定 to_me 的正经手段，但反过来也意味着
  我们一接话，对面那个机器人立刻就被「有人回复我」叫醒，两个号能一直聊下去

所以不用 ``to_me()``，改成自己认：消息里明确 @ 了我们、或者回复的正是我们发出去
的那条；私聊本来就是冲我们说的，照旧算数。另外把本进程连着的其它账号和配置里
拉黑的号一并挡在门外——机器人之间接不上话，链子就断在第一环。
"""

from nonebot import get_bots
from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna.uniseg import At, Reply, UniMessage, UniMsg, get_target

from .config import chat_config
from .recorder import recorder, scope_id

_ID_ATTRS = ("user_id", "id", "open_id", "union_id", "user_openid", "tiny_id")


def _ids_of(owner: object) -> set[str]:
    """从「某个人」的模型对象里把 id 抠出来。

    各适配器的字段名不统一（OneBot 是 ``user_id``、QQ 是 ``id``、飞书是
    ``open_id``），认不出来的就当没有，多收一个 id 也只是多挡一次。
    """
    return {str(value) for attr in _ID_ATTRS if (value := getattr(owner, attr, None))}


def _bot_ids(bot: Bot) -> set[str]:
    """一个账号在别人眼里可能是什么 id。

    ``self_id`` 未必就是群里露出来的那个：OneBot 的是 QQ 号没错，官方 QQ 的却是
    AppID、发言时用的是 ``self_info.id``，飞书则要看 ``bot_info.open_id``。
    """
    ids = {str(bot.self_id)}
    for attr in ("self_info", "bot_info"):
        try:
            owner = getattr(bot, attr, None)
        except Exception:  # QQ 的 self_info 在连接就绪前会抛
            continue
        ids |= _ids_of(owner)
    return ids


def ignored_ids() -> set[str]:
    """不跟其接话的账号：本进程连着的所有号，加上配置里拉黑的"""
    return chat_config.blacklist | {
        id_ for bot in get_bots().values() for id_ in _bot_ids(bot)
    }


def is_ignored(user_id: str) -> bool:
    return user_id in ignored_ids()


def _at_targets(bot: Bot, event: Event, msg: UniMessage) -> set[str]:
    """这条消息 @ 了谁。

    不能只看 msg：适配器判定 to_me 时，做的正是把开头/结尾那个「@机器人」从消息
    里删掉。OneBot 和 QQ 把原文留在 ``original_message`` 里，飞书没留原文、但另存
    了一份 mentions，两处都翻一遍。
    """
    if (raw := getattr(event, "original_message", None)) is not None:
        try:
            msg = UniMessage.of(raw, bot=bot)
        except Exception:
            pass

    targets = {seg.target for seg in msg if isinstance(seg, At)}
    message = getattr(getattr(event, "event", None), "message", None)
    for mention in getattr(message, "mentions", None) or []:
        targets |= _ids_of(getattr(mention, "id", None))
    return targets


def _replied_to_self(bot: Bot, event: Event, msg: UniMessage) -> bool:
    reply = next((seg for seg in msg if isinstance(seg, Reply)), None)
    if reply is None:
        return False

    # 自己发出去的消息都记了 id，缓冲里认得出来最准；重启或者翻篇之后查不到，
    # 再看适配器附在回复上的原消息是谁发的
    if (record := recorder.find(scope_id(event), reply.id)) is not None:
        return record.is_self

    origin = reply.origin
    for attr in ("sender", "author"):
        if (owner := getattr(origin, attr, None)) is not None:
            return bool(_ids_of(owner) & _bot_ids(bot))
    return False


async def should_reply(bot: Bot, event: Event, msg: UniMsg) -> bool:
    """明确在叫我们才接话：@ 了我们、回复了我们，或者干脆是私聊"""
    if is_ignored(event.get_user_id()):
        return False

    try:
        if get_target(event).private:
            return True
    except Exception:  # 认不出会话类型就按群聊处理，宁可不接话
        pass

    return bool(_at_targets(bot, event, msg) & _bot_ids(bot)) or _replied_to_self(
        bot, event, msg
    )
