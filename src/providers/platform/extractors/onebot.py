from typing import override

import nonebot
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    PrivateMessageEvent,
)

from src.providers.platform.messages import (
    MessageInfo,
    QQGroupMessageInfo,
    QQUserMessageInfo,
)
from src.providers.platform.roles import RoleLevel
from src.providers.platform.targets import QQGroupInfo, QQUserInfo, TargetType

from ._base import Extractor


class OneBotExtractor(Extractor[MessageEvent, QQUserInfo | QQGroupInfo]):
    EVENTS = (MessageEvent,)
    TARGETS = (QQUserInfo, QQGroupInfo)

    @classmethod
    @override
    def extract_user(cls, event) -> QQUserInfo:
        return QQUserInfo(type=TargetType.QQ_USER, qq_user_id=event.user_id)

    @classmethod
    @override
    def extract_group(cls, event) -> QQGroupInfo | None:
        if isinstance(event, GroupMessageEvent):
            return QQGroupInfo(type=TargetType.QQ_GROUP, qq_group_id=event.group_id)

    @classmethod
    @override
    def extract_role(cls, event) -> RoleLevel | None:
        if not isinstance(event, GroupMessageEvent):
            return

        if event.sender.role == "owner":
            return RoleLevel.OWNER
        elif event.sender.role == "admin":
            return RoleLevel.ADMIN
        elif event.sender.role == "member":
            return RoleLevel.MEMBER
        return RoleLevel.GUEST

    @classmethod
    @override
    def extract_message(cls, event) -> QQUserMessageInfo | QQGroupMessageInfo | None:
        if isinstance(event, PrivateMessageEvent):
            return QQUserMessageInfo(type=TargetType.QQ_USER, id=event.message_id)
        elif isinstance(event, GroupMessageEvent):
            return QQGroupMessageInfo(type=TargetType.QQ_GROUP, id=event.message_id)

    @classmethod
    @override
    def extract_reply_message(cls, event) -> MessageInfo | None:
        if event.reply:
            return (
                QQGroupMessageInfo(type=TargetType.QQ_GROUP, id=event.reply.message_id)
                if isinstance(event, GroupMessageEvent)
                else QQUserMessageInfo(
                    type=TargetType.QQ_USER, id=event.reply.message_id
                )
            )

    @classmethod
    @override
    async def get_target_bot(cls, target) -> Bot:
        return next(bot for bot in nonebot.get_bots().values() if isinstance(bot, Bot))

    @classmethod
    @override
    def extract_sent_message(
        cls, target, result
    ) -> QQUserMessageInfo | QQGroupMessageInfo | None:
        if isinstance(result, dict) and "message_id" in result:
            if isinstance(target, QQUserInfo):
                return QQUserMessageInfo(type=target.type, id=result["message_id"])
            else:
                return QQGroupMessageInfo(type=target.type, id=result["message_id"])
