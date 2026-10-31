from typing import Annotated, Generic, Literal, TypeAlias, TypeVar, override

from pydantic import BaseModel, Field

from src.providers.platform.targets import TargetType

ID = TypeVar("ID", int, str)


class BaseMessageInfo(BaseModel, Generic[ID]):
    """Message entity."""

    id: ID

    @property
    def key(self) -> str:
        """Identifier unique among messages of the same type"""
        return str(self.id)


class BaseQQMessageInfo(BaseMessageInfo[int]):
    """QQ client message entity."""

    peer_id: int | None = None
    """会话（好友 QQ 号或群号）。

    OneBot 的 message_id 全局唯一，不需要；Milky 的 message_seq 只在会话内唯一，要带上
    """

    @property
    @override
    def key(self) -> str:
        return str(self.id) if self.peer_id is None else f"{self.peer_id}:{self.id}"


class QQUserMessageInfo(BaseQQMessageInfo):
    """QQ message entity."""

    type: Literal[TargetType.QQ_USER]


class QQOfficialUserMessageInfo(BaseMessageInfo[str]):
    """QQ official message entity."""

    type: Literal[TargetType.QQ_OFFICIAL_USER]


class QQGuildUserMessageInfo(BaseMessageInfo[str]):
    """QQ guild message entity."""

    type: Literal[TargetType.QQGUILD_USER]


class QQGroupMessageInfo(BaseQQMessageInfo):
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
