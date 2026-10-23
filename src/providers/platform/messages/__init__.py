from typing import Annotated, Generic, Literal, TypeAlias, TypeVar

from pydantic import BaseModel, Field

from src.providers.platform.targets import TargetType

ID = TypeVar("ID", int, str)


class BaseMessageInfo(BaseModel, Generic[ID]):
    """Message entity."""

    id: ID


class QQUserMessageInfo(BaseMessageInfo[int]):
    """QQ message entity."""

    type: Literal[TargetType.QQ_USER]


class QQOfficialUserMessageInfo(BaseMessageInfo[str]):
    """QQ official message entity."""

    type: Literal[TargetType.QQ_OFFICIAL_USER]


class QQGuildUserMessageInfo(BaseMessageInfo[str]):
    """QQ guild message entity."""

    type: Literal[TargetType.QQGUILD_USER]


class QQGroupMessageInfo(BaseMessageInfo[int]):
    """QQ group message entity."""

    type: Literal[TargetType.QQ_GROUP]


class QQOfficialGroupMessageInfo(BaseMessageInfo[str]):
    """QQ official group message entity."""

    type: Literal[TargetType.QQ_OFFICIAL_GROUP]


class QQGuildChannelMessageInfo(BaseMessageInfo[str]):
    """QQ guild channel message entity."""

    type: Literal[TargetType.QQGUILD_CHANNEL]


MessageInfo: TypeAlias = Annotated[
    QQUserMessageInfo
    | QQOfficialUserMessageInfo
    | QQGuildUserMessageInfo
    | QQGroupMessageInfo
    | QQOfficialGroupMessageInfo
    | QQGuildChannelMessageInfo,
    Field(discriminator="type"),
]
