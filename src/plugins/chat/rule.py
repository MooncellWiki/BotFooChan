"""判断一条消息是不是真的在叫我们。

原来用的 ``to_me()`` 比「被 @ 或被回复」宽得多，三个适配器都还额外认两件事：

- **消息以 NICKNAME 开头**：群里另一个机器人的回答里带上「芙芙」两个字，
  我们这边就被叫醒了
- **回复了机器人发过的那条**：这是它判定 to_me 的正经手段，但反过来也意味着
  我们一接话，对面那个机器人立刻就被「有人回复我」叫醒，两个号能一直聊下去

所以不用 ``to_me()``，改成自己认：消息里明确 @ 了我们、或者回复的正是我们发出去
的那条；私聊本来就是冲我们说的，照旧算数。另外把本进程连着的其它账号和配置里
拉黑的号一并挡在门外——机器人之间接不上话，链子就断在第一环。

通用对话只兜底：别的插件（命令、链接解析）已经接了这条消息，就不再接话。光靠优先级
排最末不够——on_alconna、on_command 默认都不阻断，@ 机器人发的命令跑完照样传到
这里。nonebot 按优先级逐级处理，轮到通用对话判断时前面的都已经跑过，所以在别的
响应器开跑前给事件打个记号，判断时看记号就行。
"""

import weakref

from nonebot import get_bots
from nonebot.adapters import Bot, Event
from nonebot.matcher import Matcher
from nonebot.message import run_preprocessor
from nonebot_plugin_alconna.uniseg import Reply, UniMessage, UniMsg, get_target

from src.providers.chat_history import recorder, scope_id
from src.providers.platform.mentions import bot_ids, ids_of, mentions_bot

from .config import chat_config

PASSIVE_PLUGINS = frozenset({"chat_history"})
"""只旁听、不回话的插件，它们跑过不算「已经有别的插件接了」"""

_handled: dict[int, weakref.ref[Event]] = {}
"""被别的插件接走的事件；事件本身不能哈希，按 id 记、用弱引用核对是不是同一个"""


@run_preprocessor
async def _mark_handled(matcher: Matcher, event: Event) -> None:
    # 通用对话自己的响应器也会打上记号，但那时它的规则已经判断过了，不影响
    if matcher.plugin_id in PASSIVE_PLUGINS:
        return
    key = id(event)

    def forget(ref: weakref.ref[Event]) -> None:
        if _handled.get(key) is ref:
            del _handled[key]

    _handled[key] = weakref.ref(event, forget)


def handled_by_others(event: Event) -> bool:
    """这条消息是不是已经有别的插件接了"""
    ref = _handled.get(id(event))
    return ref is not None and ref() is event


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
    """明确在叫我们、又没有别的插件接手才接话：@ 了我们、回复了我们，或者干脆是私聊"""
    if handled_by_others(event) or is_ignored(event.get_user_id()):
        return False

    try:
        # 规则检查时还没有「当前 bot」上下文，不传 bot 会直接抛
        if get_target(event, bot).private:
            return True
    except Exception:  # 认不出会话类型就按群聊处理，宁可不接话
        pass

    return mentions_bot(bot, event, msg) or _replied_to_self(bot, event, msg)
