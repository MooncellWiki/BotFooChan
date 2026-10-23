from typing import Annotated, TypeAlias

from nonebot.params import Depends

from src.plugins.github.models import Subscription
from src.providers.platform import TARGET_INFO


async def list_subscriptions(info: TARGET_INFO) -> list[Subscription]:
    return await Subscription.from_info(info)


SUBSCRIPTIONS: TypeAlias = Annotated[list[Subscription], Depends(list_subscriptions)]
"""List subscriptions for the current event target."""
