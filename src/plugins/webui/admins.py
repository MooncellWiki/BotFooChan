"""管理员名单：.env 的 WEBUI__ADMINS 加上在管理后台里添加的。

.env 里的那几个是兜底，页面上删不掉，免得把自己锁在外面。
"""

from datetime import UTC, datetime

from nonebot import get_driver
from nonebot_plugin_orm import Model, get_session
from sqlalchemy import DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column

from src.providers.settings import audit


class WebUIAdmin(Model):
    __tablename__ = "webui_admin"

    login: Mapped[str] = mapped_column(String(64), primary_key=True)
    """GitHub 用户名，存小写"""
    note: Mapped[str] = mapped_column(String(256), default="")
    added_by: Mapped[str] = mapped_column(String(128))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


_logins: set[str] = set()
"""库里的管理员（小写），启动时加载，增删时同步"""


def db_admins() -> set[str]:
    return _logins


@get_driver().on_startup
async def _load() -> None:
    async with get_session() as session:
        _logins.update((await session.scalars(select(WebUIAdmin.login))).all())


async def list_admins() -> list[WebUIAdmin]:
    async with get_session() as session:
        return list(
            (
                await session.scalars(select(WebUIAdmin).order_by(WebUIAdmin.added_at))
            ).all()
        )


async def add_admin(login: str, note: str, actor: str) -> None:
    login = login.strip().lower()
    async with get_session() as session:
        if await session.get(WebUIAdmin, login) is not None:
            return
        session.add(
            WebUIAdmin(
                login=login, note=note, added_by=actor, added_at=datetime.now(UTC)
            )
        )
        await session.commit()
    _logins.add(login)
    await audit(actor, "admin", "add", {"login": login, "note": note})


async def remove_admin(login: str, actor: str) -> bool:
    login = login.strip().lower()
    async with get_session() as session:
        if (row := await session.get(WebUIAdmin, login)) is None:
            return False
        await session.delete(row)
        await session.commit()
    _logins.discard(login)
    await audit(actor, "admin", "remove", {"login": login})
    return True
