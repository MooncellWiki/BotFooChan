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
from nonebot_plugin_alconna.uniseg import Reply, UniMessage, UniMsg, get_target

from src.providers.chat_history import recorder, scope_id
from src.providers.platform.mentions import bot_ids, ids_of, mentions_bot

from .config import chat_config


def ignored_ids() -> set[str]:
    """不跟其接话的账号：本进程连着的所有号，加上配置里拉黑的"""
    return chat_config.blacklist | {
        id_ for bot in get_bots().values() for id_ in bot_ids(bot)
    }


def is_ignored(user_id: str) -> bool:
    return user_id in ignored_ids()


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
            return bool(ids_of(owner) & bot_ids(bot))
    return False


async def should_reply(bot: Bot, event: Event, msg: UniMsg) -> bool:
    """明确在叫我们才接话：@ 了我们、回复了我们，或者干脆是私聊"""
    if is_ignored(event.get_user_id()):
        return False

    try:
        # 规则检查时还没有「当前 bot」上下文，不传 bot 会直接抛
        if get_target(event, bot).private:
            return True
    except Exception:  # 认不出会话类型就按群聊处理，宁可不接话
        pass

    return mentions_bot(bot, event, msg) or _replied_to_self(bot, event, msg)
