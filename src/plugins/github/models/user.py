from typing import Self, cast

from nonebot_plugin_orm import Model, get_session
from pydantic import TypeAdapter
from sqlalchemy import String, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Mapped, mapped_column

from src.providers.platform import UserInfo

from ._types import CanonicalJSON


class User(Model):
    """User model"""

    id: Mapped[int] = mapped_column(primary_key=True)
    user: Mapped[dict] = mapped_column(
        CanonicalJSON, unique=True, index=True, nullable=False
    )
    access_token: Mapped[str | None] = mapped_column(String(), nullable=True)

    def to_user_info(self) -> UserInfo:
        """Convert to user info"""
        return TypeAdapter(UserInfo).validate_python(self.user)

    @classmethod
    async def from_info(cls, info: UserInfo) -> Self | None:
        """Get user model by user info"""
        sql = select(cls).where(cls.user == info.model_dump())
        async with get_session() as session:
            result = await session.execute(sql)
            return result.scalar_one_or_none()

    @classmethod
    async def create_or_update_by_info(
        cls, info: UserInfo | Self, access_token: str | None
    ) -> Self:
        """Create or update user model by user info"""
        if isinstance(info, cls):
            info = info.to_user_info()

        info = cast("UserInfo", info)

        insert_sql = insert(cls).values(
            user=info.model_dump(), access_token=access_token
        )
        update_sql = insert_sql.on_conflict_do_update(
            index_elements=[cls.user],
            set_={"access_token": insert_sql.excluded.access_token},
        ).returning(cls)

        async with get_session() as session:
            result = await session.execute(update_sql)
            user = result.scalar_one()
            await session.commit()
            await session.refresh(user)
            return user

    async def unauth(self) -> None:
        """UnAuth user"""
        self.access_token = None
        async with get_session() as session:
            session.add(self)
            await session.commit()

    @classmethod
    async def unauth_by_info(cls, info: UserInfo) -> bool:
        """UnAuth user by user info"""
        sql = update(cls).where(cls.user == info.model_dump()).values(access_token=None)
        async with get_session() as session:
            result = await session.execute(sql)
            await session.commit()
            return bool(result.rowcount)  # type: ignore  # update 实际返回 CursorResult
