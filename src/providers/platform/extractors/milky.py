from typing import override

import nonebot
from nonebot.adapters.milky import Bot, MessageEvent
from nonebot.adapters.milky.event import FriendMessageEvent, GroupMessageEvent
from nonebot.adapters.milky.model.api import MessageResponse

from src.providers.platform.messages import (
    MessageInfo,
    QQGroupMessageInfo,
    QQUserMessageInfo,
)
from src.providers.platform.roles import RoleLevel
from src.providers.platform.targets import QQGroupInfo, QQUserInfo, TargetType

from ._base import Extractor

ROLES = {"owner": RoleLevel.OWNER, "admin": RoleLevel.ADMIN, "member": RoleLevel.MEMBER}


class MilkyExtractor(Extractor[MessageEvent, QQUserInfo | QQGroupInfo]):
    """Milky 协议端（Yogurt 等）的 QQ 号/群号与 OneBot 是同一套，目标类型共用

    Milky 的 message_seq 只在单个会话里唯一，消息信息都带上会话号（peer_id）。
    """

    EVENTS = (MessageEvent,)
    TARGETS = (QQUserInfo, QQGroupInfo)

    @classmethod
    @override
    def extract_user(cls, event) -> QQUserInfo:
        return QQUserInfo(type=TargetType.QQ_USER, qq_user_id=event.data.sender_id)

    @classmethod
    @override
    def extract_group(cls, event) -> QQGroupInfo | None:
        if isinstance(event, GroupMessageEvent):
            return QQGroupInfo(type=TargetType.QQ_GROUP, qq_group_id=event.data.peer_id)

    @classmethod
    @override
    def extract_role(cls, event) -> RoleLevel | None:
        if not isinstance(event, GroupMessageEvent):
            return

        member = event.data.group_member
        return ROLES.get(member.role, RoleLevel.GUEST) if member else RoleLevel.GUEST

    @classmethod
    def _message_info(
        cls, event: MessageEvent, message_seq: int
    ) -> QQUserMessageInfo | QQGroupMessageInfo:
        if isinstance(event, GroupMessageEvent):
            return QQGroupMessageInfo(
                type=TargetType.QQ_GROUP, id=message_seq, peer_id=event.data.peer_id
            )
        return QQUserMessageInfo(
            type=TargetType.QQ_USER, id=message_seq, peer_id=event.data.peer_id
        )

    @classmethod
    @override
    def extract_message(cls, event) -> QQUserMessageInfo | QQGroupMessageInfo | None:
        if isinstance(event, FriendMessageEvent | GroupMessageEvent):
            return cls._message_info(event, event.data.message_seq)

    @classmethod
    @override
    def extract_reply_message(cls, event) -> MessageInfo | None:
        if event.reply:
            return cls._message_info(event, event.reply.message_seq)

    @classmethod
    @override
    async def get_target_bot(cls, target) -> Bot | None:
        return next(
            (bot for bot in nonebot.get_bots().values() if isinstance(bot, Bot)), None
        )

    @classmethod
    @override
    def extract_sent_message(
        cls, target, result
    ) -> QQUserMessageInfo | QQGroupMessageInfo | None:
        if not isinstance(result, MessageResponse):
            return
        if isinstance(target, QQUserInfo):
            return QQUserMessageInfo(
                type=target.type, id=result.message_seq, peer_id=target.qq_user_id
            )
        return QQGroupMessageInfo(
            type=target.type, id=result.message_seq, peer_id=target.qq_group_id
        )
