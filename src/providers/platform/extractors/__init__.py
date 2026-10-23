from typing import Any, cast

from nonebot.adapters import Bot, Event

from src.providers.platform.messages import MessageInfo
from src.providers.platform.roles import RoleLevel
from src.providers.platform.targets import GroupInfo, TargetInfo, UserInfo

from ._base import Extractor as Extractor
from .onebot import OneBotExtractor as OneBotExtractor
from .qq import QQExtractor as QQExtractor

EXTRACTORS = cast("tuple[type[Extractor], ...]", (OneBotExtractor, QQExtractor))


def is_supported_event(event: Event) -> bool:
    """Check if the event can be handled by any extractor."""
    return any(isinstance(event, extractor.EVENTS) for extractor in EXTRACTORS)  # type: ignore


def extract_user(event: Event) -> UserInfo | None:
    for extractor in EXTRACTORS:
        if isinstance(event, extractor.EVENTS):  # type: ignore
            return extractor.extract_user(event)


def extract_group(event: Event) -> GroupInfo | None:
    for extractor in EXTRACTORS:
        if isinstance(event, extractor.EVENTS):  # type: ignore
            return extractor.extract_group(event)


def extract_target(event: Event) -> TargetInfo | None:
    for extractor in EXTRACTORS:
        if isinstance(event, extractor.EVENTS):  # type: ignore
            return extractor.extract_target(event)


def extract_is_private(event: Event) -> bool | None:
    for extractor in EXTRACTORS:
        if isinstance(event, extractor.EVENTS):  # type: ignore
            return extractor.extract_is_private(event)


def extract_role(event: Event) -> RoleLevel | None:
    for extractor in EXTRACTORS:
        if isinstance(event, extractor.EVENTS):  # type: ignore
            return extractor.extract_role(event)


def extract_message(event: Event) -> MessageInfo | None:
    for extractor in EXTRACTORS:
        if isinstance(event, extractor.EVENTS):  # type: ignore
            return extractor.extract_message(event)


def extract_reply_message(event: Event) -> MessageInfo | None:
    for extractor in EXTRACTORS:
        if isinstance(event, extractor.EVENTS):  # type: ignore
            return extractor.extract_reply_message(event)


async def get_target_bot(target: TargetInfo) -> Bot | None:
    for extractor in EXTRACTORS:
        if isinstance(target, extractor.TARGETS):  # type: ignore
            return await extractor.get_target_bot(target)


def extract_sent_message(target: TargetInfo, result: Any) -> MessageInfo | None:
    for extractor in EXTRACTORS:
        if isinstance(target, extractor.TARGETS):  # type: ignore
            return extractor.extract_sent_message(target, result)
