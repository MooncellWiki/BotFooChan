from nonebot_plugin_alconna import (
    Alconna,
    AlconnaMatch,
    AlconnaMatches,
    Args,
    Arparma,
    CommandMeta,
    Match,
    on_alconna,
)

from .dice.rd import rd0

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


@rd_matcher.handle()
async def rd_handler(
    result: Arparma = AlconnaMatches(), a_number: Match = AlconnaMatch("a_number")
):
    if "h" in (pattern := result.header["dabp"].strip()):
        return

    exp: int | None = a_number.result if a_number.available else None
    if pattern.startswith("a"):
        if pattern[1:].isdigit() and exp is None:
            exp = int(pattern[1:])
        pattern = "1d100"

    rule = 0
    await rd_matcher.finish(rd0(pattern, exp, rule))
