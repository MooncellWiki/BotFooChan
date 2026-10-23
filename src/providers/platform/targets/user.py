# 子类收窄父类字段的类型是有意为之（pydantic 判别字段、已授权/已绑定的模型），
# 原版在全局关了这条检查
# pyright: reportIncompatibleVariableOverride=false

import abc
from typing import Annotated, Literal, TypeAlias

from pydantic import Field

from ._base import BaseTargetInfo, TargetType


class BaseUserInfo(abc.ABC, BaseTargetInfo):
    """User entity."""

    type: Literal[
        TargetType.QQ_USER, TargetType.QQ_OFFICIAL_USER, TargetType.QQGUILD_USER
    ]

    @property
    @abc.abstractmethod
    def user_id(self) -> str:
        """User id to show"""
        raise NotImplementedError


class QQUserInfo(BaseUserInfo):
    """QQ user entity."""

    type: Literal[TargetType.QQ_USER]
    qq_user_id: int

    @property
    def user_id(self) -> str:
        return str(self.qq_user_id)


class QQOfficialUserInfo(BaseUserInfo):
    """QQ official user entity."""

    type: Literal[TargetType.QQ_OFFICIAL_USER]
    qq_user_open_id: str

    @property
    def user_id(self) -> str:
        return self.qq_user_open_id


class QQGuildUserInfo(BaseUserInfo):
    """QQ guild user entity."""

    type: Literal[TargetType.QQGUILD_USER]
    qqguild_user_id: str

    @property
    def user_id(self) -> str:
        return self.qqguild_user_id


UserInfo: TypeAlias = Annotated[
    QQUserInfo | QQOfficialUserInfo | QQGuildUserInfo, Field(discriminator="type")
]
