from typing import Self, cast

from nonebot_plugin_orm import Model, get_session
from pydantic import TypeAdapter
from sqlalchemy import String, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Mapped, mapped_column

from src.providers.platform import GroupInfo

from ._types import CanonicalJSON


class Group(Model):
    """Group model"""

    id: Mapped[int] = mapped_column(primary_key=True)
    group: Mapped[dict] = mapped_column(
        CanonicalJSON, unique=True, index=True, nullable=False
    )
    bind_repo: Mapped[str | None] = mapped_column(String(), nullable=True)

    def to_group_info(self) -> GroupInfo:
        """Convert to group info"""
        return TypeAdapter(GroupInfo).validate_python(self.group)

    @classmethod
    async def from_info(cls, info: GroupInfo) -> Self | None:
        """Get group model by group info"""
        sql = select(cls).where(cls.group == info.model_dump())
        async with get_session() as session:
            result = await session.execute(sql)
            return result.scalar_one_or_none()

    @classmethod
    async def create_or_update_by_info(
        cls, info: GroupInfo | Self, bind_repo: str | None
    ) -> Self:
        """Create or update group model by group info"""
        if isinstance(info, cls):
            info = info.to_group_info()

        info = cast("GroupInfo", info)

        insert_sql = insert(cls).values(group=info.model_dump(), bind_repo=bind_repo)
        update_sql = insert_sql.on_conflict_do_update(
            index_elements=[cls.group],
            set_={"bind_repo": insert_sql.excluded.bind_repo},
        ).returning(cls)

        async with get_session() as session:
            result = await session.execute(update_sql)
            group = result.scalar_one()
            await session.commit()
            await session.refresh(group)
            return group

    async def unbind(self) -> None:
        """Unbind group and repo"""
        self.bind_repo = None
        async with get_session() as session:
            session.add(self)
            await session.commit()

    @classmethod
    async def unbind_by_info(cls, info: GroupInfo) -> bool:
        """Unbind group and repo by group info"""
        sql = update(cls).where(cls.group == info.model_dump()).values(bind_repo=None)
        async with get_session() as session:
            result = await session.execute(sql)
            await session.commit()
            return bool(result.rowcount)  # type: ignore  # update 实际返回 CursorResult
