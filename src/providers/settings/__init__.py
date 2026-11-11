"""运行时配置：插件的行为配置存进数据库，管理后台改完立即生效。

插件在 config.py 里用 :func:`register` 登记自己的配置段，拿回一个和原来同类型的
对象（其实是代理，每次取属性都读当前生效的值），调用处的 ``chat_config.model``
之类不用改。

- 启动前（数据库还没准备好）、以及没配 WEBUI__SECRET_KEY 时，读的是 .env 里的值
- 启动时库里还没有某一段，就用 .env 的值初始化并记一条审计；之后以库为准，
  .env 里对应的项不再生效
- 密钥加密后存库；只在启动时读一次的字段标了 ``restart``，见 :mod:`.fields`

适配器、端口、数据库这类基础设施配置不归这里管，仍然只在 .env 里。
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
import inspect
from typing import Any, Literal, cast

from nonebot import get_driver, logger, require
from pydantic import BaseModel

require("nonebot_plugin_orm")
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from . import crypto, fields
from .fields import UnknownSecret as UnknownSecret
from .models import AuditLog as AuditLog
from .models import SettingsDoc as SettingsDoc

SYSTEM = "system"

Listener = Callable[[Any, Any], Awaitable[None] | None]
"""配置变更回调，收到 (旧值, 新值)"""


@dataclass(eq=False)
class Section:
    key: str
    model: type[BaseModel]
    title: str
    description: str
    env: Callable[[], BaseModel]
    value: BaseModel
    source: Literal["env", "database"] = "env"
    updated_at: datetime | None = None
    updated_by: str | None = None
    listeners: list[Listener] = field(default_factory=list)

    def masked(self) -> dict[str, Any]:
        return fields.mask(self.model, self.value.model_dump(mode="json"))


class _Proxy:
    """转发到配置段当前的值，换了值也不用重新导入"""

    __slots__ = ("_section",)

    def __init__(self, section: Section) -> None:
        object.__setattr__(self, "_section", section)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._section.value, name)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("配置是只读的，要改请用 settings.save / settings.patch")

    def __repr__(self) -> str:
        return f"<settings {self._section.key}: {self._section.value!r}>"


_sections: dict[str, Section] = {}
_persistent = False


def register[T: BaseModel](
    key: str, model: type[T], *, title: str, env: Callable[[], T], description: str = ""
) -> T:
    """登记一个配置段，返回读取它的代理对象（类型上就是 model 的实例）。

    env 给出 .env 里的值（通常是 ``get_plugin_config(...)``），用作库里还没有时的初值。
    """
    if key in _sections:
        raise ValueError(f"配置段 {key} 已经登记过了")
    section = Section(key, model, title, description, env, env())
    _sections[key] = section
    return cast("T", _Proxy(section))


def sections() -> list[Section]:
    return list(_sections.values())


def get_section(key: str) -> Section:
    if key not in _sections:
        raise KeyError(f"没有叫 {key} 的配置段")
    return _sections[key]


def persistent() -> bool:
    """配置已经从库里加载、可以写库（启动完成且配了 WEBUI__SECRET_KEY）"""
    return _persistent


def on_change[L: Listener](key: str) -> Callable[[L], L]:
    """登记配置变更回调（装饰器），回调收到 (旧值, 新值)"""

    def decorator(listener: L) -> L:
        get_section(key).listeners.append(listener)
        return listener

    return decorator


async def _notify(section: Section, old: BaseModel, new: BaseModel) -> None:
    for listener in section.listeners:
        try:
            result = listener(old, new)
            if inspect.isawaitable(result):
                await result
        except Exception as e:
            logger.opt(exception=e).error(f"配置段 {section.key} 的变更回调出错")


class NotPersistentError(RuntimeError):
    """配置还没从库里加载，或者没配 WEBUI__SECRET_KEY"""


async def save(
    key: str, data: dict[str, Any], *, actor: str, action: str = "update"
) -> BaseModel:
    """整段替换。打码的密钥（接口给出去的值）沿用原值。

    校验不过抛 pydantic 的 ValidationError，打码值对不上原值抛 UnknownSecret。
    """
    if not _persistent:
        raise NotPersistentError(
            "配置没从数据库加载（没配 WEBUI__SECRET_KEY？），改不了"
        )
    section = get_section(key)
    old_plain = section.value.model_dump(mode="json")
    new_value = section.model.model_validate(
        fields.restore(section.model, data, old_plain)
    )
    new_plain = new_value.model_dump(mode="json")
    changes = fields.diff(
        fields.mask(section.model, old_plain), fields.mask(section.model, new_plain)
    )
    if not changes:
        return section.value

    now = datetime.now(UTC)
    async with get_session() as session:
        doc = await session.get(SettingsDoc, key)
        stored = fields.encrypt(section.model, new_plain)
        if doc is None:
            session.add(
                SettingsDoc(key=key, value=stored, updated_at=now, updated_by=actor)
            )
        else:
            doc.value = stored
            doc.updated_at = now
            doc.updated_by = actor
        session.add(
            AuditLog(
                at=now,
                actor=actor,
                entity=f"settings:{key}",
                action=action,
                detail={"changes": changes},
            )
        )
        await session.commit()

    old_value = section.value
    section.value = new_value
    section.source = "database"
    section.updated_at = now
    section.updated_by = actor
    logger.info(f"配置段 {key} 已由 {actor} 修改：{', '.join(changes)}")
    await _notify(section, old_value, new_value)
    return new_value


async def patch(
    key: str, changes: dict[str, Any], *, actor: str, action: str = "update"
) -> BaseModel:
    """只改顶层的几个字段"""
    data = get_section(key).value.model_dump(mode="json")
    data.update(changes)
    return await save(key, data, actor=actor, action=action)


async def audit(
    actor: str, entity: str, action: str, detail: dict[str, Any] | None = None
) -> None:
    """记一条审计（配置以外的管理操作，如删订阅、改群友记忆）"""
    async with get_session() as session:
        session.add(
            AuditLog(
                at=datetime.now(UTC),
                actor=actor,
                entity=entity,
                action=action,
                detail=detail or {},
            )
        )
        await session.commit()


@get_driver().on_startup
async def _load_all() -> None:
    """从库里加载各配置段；库里还没有的用 .env 的值初始化"""
    global _persistent
    if not crypto.available():
        logger.warning(
            "没配 WEBUI__SECRET_KEY：插件配置继续从 .env 读，管理后台里改不了"
        )
        return

    async with get_session() as session:
        docs = {d.key: d for d in (await session.scalars(select(SettingsDoc))).all()}

    now = datetime.now(UTC)
    seeded: list[Section] = []
    for section in _sections.values():
        if (doc := docs.get(section.key)) is None:
            seeded.append(section)
            continue
        try:
            value = section.model.model_validate(
                fields.decrypt(section.model, doc.value)
            )
        except Exception as e:
            logger.opt(exception=e).error(
                f"配置段 {section.key} 在库里的内容读不出来，先用 .env 里的值"
            )
            continue
        old_value = section.value
        section.value = value
        section.source = "database"
        section.updated_at = doc.updated_at
        section.updated_by = doc.updated_by
        if value != old_value:
            logger.info(
                f"配置段 {section.key} 以数据库为准（.env 里的对应项已不再生效）"
            )
            await _notify(section, old_value, value)

    if seeded:
        async with get_session() as session:
            for section in seeded:
                plain = section.value.model_dump(mode="json")
                session.add(
                    SettingsDoc(
                        key=section.key,
                        value=fields.encrypt(section.model, plain),
                        updated_at=now,
                        updated_by=SYSTEM,
                    )
                )
                session.add(
                    AuditLog(
                        at=now,
                        actor=SYSTEM,
                        entity=f"settings:{section.key}",
                        action="seed",
                        detail={"from": ".env"},
                    )
                )
                section.source = "database"
                section.updated_at = now
                section.updated_by = SYSTEM
            await session.commit()
        logger.info(
            "以下配置段库里还没有，已用 .env 的值初始化："
            + "、".join(s.key for s in seeded)
        )
    _persistent = True
