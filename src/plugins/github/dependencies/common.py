from typing import Any

from nonebot.matcher import Matcher
from nonebot.params import Depends, RegexDict
from nonebot.typing import T_State


async def store_regex_vars(state: T_State, group: dict[str, Any] = RegexDict()):
    state.update(group)


STORE_REGEX_VARS = Depends(store_regex_vars)
"""Parameterless dependency that stores regex variables in the state."""


def bypass_key(key: Any):
    """Bypass handler run if the given key is in the state.

    Args:
        key: Key to check.
    """

    async def bypass_key_dependency(matcher: Matcher, state: T_State) -> None:
        if key in state:
            matcher.skip()

    return Depends(bypass_key_dependency)


def bypass_arg(arg: str):
    """Bypass handler run if the given arg is in the state.

    Args:
        arg: Arg to check.
    """

    async def bypass_arg_dependency(matcher: Matcher) -> None:
        if matcher.get_arg(arg, None) is not None:
            matcher.skip()

    return Depends(bypass_arg_dependency)
