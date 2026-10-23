# 子类收窄父类字段的类型是有意为之（pydantic 判别字段、已授权/已绑定的模型），
# 原版在全局关了这条检查
# pyright: reportIncompatibleVariableOverride=false

from typing import Annotated, Literal, TypeAlias

from pydantic import Field

from ._base import BaseTargetInfo, TargetType


class BaseGroupInfo(BaseTargetInfo):
    """Group entity."""

    type: Literal[
        TargetType.QQ_GROUP, TargetType.QQ_OFFICIAL_GROUP, TargetType.QQGUILD_CHANNEL
    ]


class QQGroupInfo(BaseGroupInfo):
    """QQ group entity."""

    type: Literal[TargetType.QQ_GROUP]
    qq_group_id: int


class QQOfficialGroupInfo(BaseGroupInfo):
    """QQ official group entity."""

    type: Literal[TargetType.QQ_OFFICIAL_GROUP]
    qq_group_open_id: str


class QQGuildChannelInfo(BaseGroupInfo):
    """QQ guild channel entity."""

    type: Literal[TargetType.QQGUILD_CHANNEL]
    qq_guild_id: str
    qq_channel_id: str


GroupInfo: TypeAlias = Annotated[
    QQGroupInfo | QQOfficialGroupInfo | QQGuildChannelInfo, Field(discriminator="type")
]
