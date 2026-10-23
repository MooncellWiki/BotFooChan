# 原版的 action 是 Postgres 数组，合并、扣除都写在 SQL 里（unnest + array_agg）。
# SQLite 没有数组，这里存成 JSON 列表，合并和扣除挪到 Python 里做，语义如下：
#
# - action 为 NULL：订阅该事件的全部 action
# - action 为 []：已退订（行还留着，列订阅时跳过）
# - 其余：只订阅列出来的这些 action
#
# 顺手修了原版退订的两处问题：扣掉最后一个 action 时 array_agg 得到 NULL，反而变成
# 订阅全部；按事件整体退订（不带 action）一个「订阅全部」的事件时，CASE 先命中
# 「原值为 NULL 则不动」，结果什么也没退掉。

from typing import Self, TypedDict, cast

from nonebot_plugin_orm import Model, get_session
from pydantic import TypeAdapter
from sqlalchemy import JSON, Index, String, UniqueConstraint, select, update
from sqlalchemy.orm import Mapped, mapped_column

from src.providers.platform import TargetInfo

from ._types import CanonicalJSON


class SubData(TypedDict):
    """Subscription data"""

    owner: str
    repo: str
    event: str
    action: list[str] | None


UNIQUE_SUBSCRIPTION = UniqueConstraint("subscriber", "owner", "repo", "event")


class Subscription(Model):
    """GitHub event subscription model"""

    __table_args__ = (
        Index(None, "owner", "repo", "event"),
        UNIQUE_SUBSCRIPTION,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscriber: Mapped[dict] = mapped_column(CanonicalJSON, index=True, nullable=False)
    owner: Mapped[str] = mapped_column(String(), nullable=False)
    repo: Mapped[str] = mapped_column(String(), nullable=False)
    event: Mapped[str] = mapped_column(String(), nullable=False)
    # none_as_null：None 要存成 SQL NULL（订阅全部），而不是 JSON 的 "null"
    action: Mapped[list[str] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )

    def to_subscriber_info(self) -> TargetInfo:
        """Convert to subscriber info"""
        return TypeAdapter(TargetInfo).validate_python(self.subscriber)

    @classmethod
    async def from_info(cls, info: TargetInfo) -> list[Self]:
        """List subscriptions by subscriber info"""
        sql = select(cls).where(cls.subscriber == info.model_dump())
        async with get_session() as session:
            result = await session.execute(sql)
            return list(result.scalars().all())

    @classmethod
    async def subscribe_by_info(
        cls, info: TargetInfo | Self, *subsciptions: SubData
    ) -> None:
        """Create or update user subscriptions by user info"""
        if isinstance(info, cls):
            info = info.to_subscriber_info()

        info = cast("TargetInfo", info)
        subscriber = info.model_dump()

        async with get_session() as session:
            for subscription in subsciptions:
                existing = await session.scalar(
                    select(cls).where(
                        cls.subscriber == subscriber,
                        cls.owner == subscription["owner"],
                        cls.repo == subscription["repo"],
                        cls.event == subscription["event"],
                    )
                )
                if existing is None:
                    session.add(cls(subscriber=subscriber, **subscription))
                # either side subscribes all actions
                elif subscription["action"] is None or existing.action is None:
                    existing.action = None
                # merge and deduplicate actions
                else:
                    existing.action = sorted(
                        {*existing.action, *subscription["action"]}
                    )
            await session.commit()

    @classmethod
    async def unsubscribe_by_info(
        cls, info: TargetInfo | Self, *unsubsciptions: SubData
    ) -> None:
        """Delete user subscription by user info"""
        if isinstance(info, cls):
            info = info.to_subscriber_info()

        info = cast("TargetInfo", info)
        subscriber = info.model_dump()

        async with get_session() as session:
            for unsubscription in unsubsciptions:
                existing = await session.scalar(
                    select(cls).where(
                        cls.subscriber == subscriber,
                        cls.owner == unsubscription["owner"],
                        cls.repo == unsubscription["repo"],
                        cls.event == unsubscription["event"],
                    )
                )
                if existing is None:
                    continue
                # remove all actions if unsubscription["action"] is None
                if unsubscription["action"] is None:
                    existing.action = []
                # all actions are subscribed, cannot remove some of them
                elif existing.action is None:
                    continue
                # remove any value in unsubscription["action"]
                else:
                    existing.action = [
                        action
                        for action in existing.action
                        if action not in unsubscription["action"]
                    ]
            await session.commit()

    @classmethod
    async def unsubscribe_all_by_info(
        cls, info: TargetInfo | Self, owner: str, repo: str
    ) -> None:
        """Delete all user subscriptions of the repo by user info"""
        if isinstance(info, cls):
            info = info.to_subscriber_info()

        info = cast("TargetInfo", info)

        clear_sql = (
            update(cls)
            .where(
                cls.subscriber == info.model_dump(),
                cls.owner == owner,
                cls.repo == repo,
            )
            # set to empty array
            .values(action=[])
        )
        async with get_session() as session:
            await session.execute(clear_sql)
            await session.commit()

    @classmethod
    async def list_subscribers(
        cls, owner: str, repo: str, event: str, action: str | None = None
    ) -> list[Self]:
        """List subscribers from repo webhook event name"""
        list_sql = select(cls).where(
            cls.owner == owner, cls.repo == repo, cls.event == event
        )
        async with get_session() as session:
            result = await session.execute(list_sql)
            subscriptions = result.scalars().all()

        # action is NULL means all actions are subscribed,
        # otherwise the action list should contain the event action
        return [
            sub
            for sub in subscriptions
            if sub.action is None or (action is not None and action in sub.action)
        ]
