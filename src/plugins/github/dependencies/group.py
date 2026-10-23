# 子类收窄父类字段的类型是有意为之（pydantic 判别字段、已授权/已绑定的模型），
# 原版在全局关了这条检查
# pyright: reportIncompatibleVariableOverride=false

from typing import TYPE_CHECKING, Annotated, TypeAlias

from nonebot.matcher import Matcher
from nonebot.params import Depends

from src.plugins.github.models import Group
from src.providers.platform import GROUP_INFO, OPTIONAL_GROUP_INFO, OPTIONAL_IS_PRIVATE


async def run_when_private(matcher: Matcher, is_private: OPTIONAL_IS_PRIVATE) -> None:
    """Skip the matcher if the event is not a private event"""
    if is_private is not True:
        matcher.skip()


RUN_WHEN_PRIVATE = Depends(run_when_private)
"""Parameterless dependency to skip the matcher if the event is not a private event"""


async def run_when_group(matcher: Matcher, group_info: OPTIONAL_GROUP_INFO) -> None:
    """Skip the matcher if the event is not a group event"""
    if group_info is None:
        matcher.skip()


RUN_WHEN_GROUP = Depends(run_when_group)
"""Parameterless dependency to skip the matcher if the event is not a group event"""


async def get_current_group(group: GROUP_INFO) -> Group | None:
    """Get current database group from event."""
    return await Group.from_info(group)


GROUP: TypeAlias = Annotated[Group | None, Depends(get_current_group)]
"""Current database group from event. None if never binded."""


if TYPE_CHECKING:

    class BindedGroup(Group):
        """Binded group model"""

        bind_repo: str

else:
    BindedGroup = Group


async def get_binded_group(matcher: Matcher, group: GROUP) -> BindedGroup:
    """Get current database group from event.

    Finish the session if user is not binded.
    """
    if not group or not group.bind_repo:
        await matcher.finish("本群还没有绑定仓库，请使用 /bind 进行绑定")
    return group  # type: ignore


BINDED_GROUP: TypeAlias = Annotated[BindedGroup, Depends(get_binded_group)]
"""Current database group from event. Finish the session if group is not binded."""
