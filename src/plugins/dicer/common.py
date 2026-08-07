from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import (
    Alconna,
    AlconnaMatch,
    AlconnaMatches,
    Args,
    Arparma,
    At,
    CommandMeta,
    Match,
    MsgTarget,
    MultiVar,
    Target,
    UniMessage,
    on_alconna,
)

from . import constant
from .cards import cache_cards, del_handler, sa_handler, set_handler, show_handler
from .dices import en, rd0, st
from .investigator import Investigator
from .madness import li, ti
from .san_check import sc

rd_matcher = on_alconna(
    Alconna(
        [".", "/"],
        "r( )?{dabp}",
        Args["a_number", int | None],
        meta=CommandMeta(compact=True),
    ),
)
rhd_matcher = on_alconna(
    Alconna(
        [".", "/"],
        "rh( )?{dabp}",
        Args["a_number", int | None],
        meta=CommandMeta(compact=True),
    ),
)
# /help 由 treehelp 提供，此处仅注册 "." 前缀避免冲突
help_matcher = on_alconna(
    Alconna(["."], "help", Args["item?", str], meta=CommandMeta(compact=True))
)
st_matcher = on_alconna(Alconna([".", "/"], "st"))
en_matcher = on_alconna(Alconna([".", "/"], "en", Args["level?", str]))
ti_matcher = on_alconna(Alconna([".", "/"], "ti"))
li_matcher = on_alconna(Alconna([".", "/"], "li"))
coc_matcher = on_alconna(
    Alconna(
        [".", "/"],
        "coc",
        Args["age", int | None],
        meta=CommandMeta(compact=True),
    ),
)
sc_matcher = on_alconna(Alconna([".", "/"], "sc", Args["sf?", str]["san?", int]))
set_matcher = on_alconna(Alconna([".", "/"], "set", Args["name?", str]["value?", str]))
show_matcher = on_alconna(Alconna([".", "/"], "show", Args["at?", At]))
shows_matcher = on_alconna(Alconna([".", "/"], "shows", Args["at?", At]))
sa_matcher = on_alconna(Alconna([".", "/"], "sa", Args["attr?", str]))
del_matcher = on_alconna(Alconna([".", "/"], "del", Args["items", MultiVar(str, "*")]))


def _group_id(target: Target) -> str:
    """适配器无关的群组标识，私聊统一归入 "0" """
    if target.private:
        return "0"
    if target.channel and target.parent_id:
        return f"{target.parent_id}_{target.id}"
    return target.id


def _pattern_roll(pattern: str, a_number: Match) -> str:
    exp: int | None = a_number.result if a_number.available else None
    if pattern.startswith("a"):
        if pattern[1:].isdigit() and exp is None:
            exp = int(pattern[1:])
        pattern = "1d100"

    rule = 0
    return rd0(pattern, exp, rule)


@rd_matcher.handle()
async def rd_handler(
    result: Arparma = AlconnaMatches(), a_number: Match = AlconnaMatch("a_number")
):
    if "h" in (pattern := result.header["dabp"].strip()):
        return

    try:
        msg = _pattern_roll(pattern, a_number)
    except ValueError, ZeroDivisionError:
        msg = constant.r
    await rd_matcher.finish(msg)


@rhd_matcher.handle()
async def rhd_handler(
    bot: Bot,
    event: Event,
    target: MsgTarget,
    result: Arparma = AlconnaMatches(),
    a_number: Match = AlconnaMatch("a_number"),
):
    try:
        msg = _pattern_roll(result.header["dabp"].strip(), a_number)
    except ValueError, ZeroDivisionError:
        await rhd_matcher.finish(constant.r)

    if target.private:
        await rhd_matcher.finish(msg)
    try:
        await UniMessage.text(msg).send(
            target=Target(event.get_user_id(), private=True, self_id=bot.self_id),
            bot=bot,
        )
    except Exception:
        await rhd_matcher.finish("暗骰失败，请确认机器人能够向你发送私聊消息")
    await rhd_matcher.finish("暗骰结果已私聊发送")


_help_topics = {
    "r": constant.r,
    "sc": constant.sc,
    "set": constant.set,
    "show": constant.show,
    "sa": constant.sa,
    "en": constant.en,
    "del": constant.del_,
    "del_": constant.del_,
}


@help_matcher.handle()
async def help_handler(item: Match = AlconnaMatch("item")):
    topic = item.result.strip().lower() if item.available else ""
    await help_matcher.finish(_help_topics.get(topic, constant.main))


@st_matcher.handle()
async def st_handler():
    await st_matcher.finish(st())


@en_matcher.handle()
async def en_handler(level: Match = AlconnaMatch("level")):
    if not level.available or not level.result.isdigit():
        await en_matcher.finish(constant.en)
    await en_matcher.finish(en(int(level.result)))


@ti_matcher.handle()
async def ti_handler():
    await ti_matcher.finish(ti())


@li_matcher.handle()
async def li_handler():
    await li_matcher.finish(li())


@coc_matcher.handle()
async def coc_handler(
    event: Event, target: MsgTarget, age: Match = AlconnaMatch("age")
):
    age_value = age.result if age.available and age.result is not None else 20
    inv = Investigator()
    msg = inv.age_change(age_value)
    if 15 <= age_value < 90:
        cache_cards.update(_group_id(target), event.get_user_id(), inv, save=False)
        msg += "\n" + inv.output()
    await coc_matcher.finish(msg)


@sc_matcher.handle()
async def sc_handler(
    event: Event,
    target: MsgTarget,
    sf: Match = AlconnaMatch("sf"),
    san: Match = AlconnaMatch("san"),
):
    await sc_matcher.finish(
        sc(
            sf.result.lower() if sf.available else None,
            san.result if san.available else None,
            _group_id(target),
            event.get_user_id(),
        )
    )


@set_matcher.handle()
async def set_cmd_handler(
    event: Event,
    target: MsgTarget,
    name: Match = AlconnaMatch("name"),
    value: Match = AlconnaMatch("value"),
):
    await set_matcher.finish(
        set_handler(
            _group_id(target),
            event.get_user_id(),
            name.result.lower() if name.available else None,
            value.result if value.available else None,
        )
    )


@show_matcher.handle()
async def show_cmd_handler(
    event: Event, target: MsgTarget, at: Match = AlconnaMatch("at")
):
    for msg in show_handler(
        _group_id(target),
        event.get_user_id(),
        at.result.target if at.available else None,
        skills=False,
    ):
        await show_matcher.send(msg)


@shows_matcher.handle()
async def shows_cmd_handler(
    event: Event, target: MsgTarget, at: Match = AlconnaMatch("at")
):
    for msg in show_handler(
        _group_id(target),
        event.get_user_id(),
        at.result.target if at.available else None,
        skills=True,
    ):
        await shows_matcher.send(msg)


@sa_matcher.handle()
async def sa_cmd_handler(
    event: Event, target: MsgTarget, attr: Match = AlconnaMatch("attr")
):
    await sa_matcher.finish(
        sa_handler(
            _group_id(target),
            event.get_user_id(),
            attr.result.lower() if attr.available else None,
        )
    )


@del_matcher.handle()
async def del_cmd_handler(
    event: Event, target: MsgTarget, items: Match = AlconnaMatch("items")
):
    args = tuple(s.lower() for s in items.result) if items.available else ()
    for msg in del_handler(_group_id(target), event.get_user_id(), args):
        await del_matcher.send(msg)
