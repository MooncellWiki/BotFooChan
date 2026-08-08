"""从上游 nonebot-bison 插件迁移已有数据

上游插件和本插件的表结构完全一致（表名也沿用 ``nonebot_bison_*``），差别只有两处：

1. 上游用 nonebot-plugin-datastore，数据库固定在 ``<datastore 数据目录>/data.db``；
   本插件用 nonebot-plugin-orm，默认库是另一个文件。
2. 上游用 saa 序列化发送目标，本插件用 uniseg 的 ``Target``，``user_target``
   这一列的 JSON 结构不同。

两步迁移都是幂等的：库里已经有订阅时不再从旧库搬，``user_target`` 已经是新格式时
不再转换。
"""

from pathlib import Path
from typing import Any

import nonebot
from nonebot.log import logger
from nonebot_plugin_alconna.uniseg import SupportScope
from nonebot_plugin_alconna.uniseg import Target as SendTarget
from nonebot_plugin_orm import get_session
from sqlalchemy import func, insert, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from .db_model import Cookie, CookieTarget, ScheduleTimeWeight, Subscribe, Target, User
from .utils import dump_send_target

# 有外键依赖，顺序不能变
_MIGRATE_ORDER = (Target, User, Subscribe, ScheduleTimeWeight, Cookie, CookieTarget)


def _legacy_db_path() -> Path | None:
    """定位上游插件（nonebot-plugin-datastore）的数据库文件"""
    global_config = nonebot.get_driver().config

    # 用户显式配了库地址就不猜了，这种情况交给用户自己处理
    if getattr(global_config, "datastore_database_url", None):
        return None

    if data_dir := getattr(global_config, "datastore_data_dir", None):
        return Path(data_dir) / "data.db"

    from nonebot_plugin_localstore import get_data_dir

    return Path(get_data_dir("")) / "data.db"


async def _migrate_from_datastore() -> None:
    legacy_db = _legacy_db_path()
    if not legacy_db or not legacy_db.is_file():
        return

    # 任何一张表里已经有数据就认为迁移过了。只看 User 是不够的：
    # 旧库里可能只有 Cookie（还没加订阅），那样每次启动都会把 Cookie 再抄一遍
    async with get_session() as session:
        for model in _MIGRATE_ORDER:
            if await session.scalar(select(func.count()).select_from(model)):
                return

    engine = create_async_engine(f"sqlite+aiosqlite:///{legacy_db}")
    try:
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
        if missing := {m.__tablename__ for m in _MIGRATE_ORDER} - tables:
            logger.debug(f"旧数据库 {legacy_db} 中没有 {missing}，跳过迁移")
            return

        # 表结构一致，直接用本插件的 ORM 模型读旧库，省掉手写类型转换
        rows: dict[type, list[dict[str, Any]]] = {}
        async with AsyncSession(engine) as legacy_session:
            for model in _MIGRATE_ORDER:
                objs = (await legacy_session.scalars(select(model))).all()
                rows[model] = [
                    {c.name: getattr(obj, c.name) for c in model.__table__.columns}
                    for obj in objs
                ]
    finally:
        await engine.dispose()

    if not any(rows.values()):
        return

    async with get_session() as session:
        for model in _MIGRATE_ORDER:
            if rows[model]:
                # 保留原主键，否则 Subscribe/CookieTarget 的外键会指错
                await session.execute(insert(model.__table__), rows[model])
        await session.commit()

    logger.success(
        "已从 {} 迁移订阅数据：{}".format(
            legacy_db,
            "，".join(f"{m.__tablename__} {len(rows[m])} 条" for m in _MIGRATE_ORDER),
        )
    )


def _convert_saa_target(data: dict[str, Any]) -> SendTarget | None:
    """把 saa 的 ``PlatformTarget`` 序列化结果转成 uniseg 的 ``Target``"""
    match data.get("platform_type"):
        case "QQ Group":
            return SendTarget(
                str(data["group_id"]),
                scope=SupportScope.qq_client,
            )
        case "QQ Private":
            return SendTarget(
                str(data["user_id"]),
                private=True,
                scope=SupportScope.qq_client,
            )
        case "QQ Group OpenID":
            return SendTarget(
                data["group_openid"],
                self_id=data.get("bot_id"),
                scope=SupportScope.qq_api,
            )
        case "QQ Private OpenID":
            return SendTarget(
                data["user_openid"],
                private=True,
                self_id=data.get("bot_id"),
                scope=SupportScope.qq_api,
            )
        case "QQ Guild Channel":
            return SendTarget(
                str(data["channel_id"]),
                channel=True,
                scope=SupportScope.qq_api,
            )
        case "QQ Guild Direct":
            return SendTarget(
                str(data["recipient_id"]),
                str(data["source_guild_id"]),
                channel=True,
                private=True,
                scope=SupportScope.qq_api,
            )
        case "Feishu Group":
            return SendTarget(data["chat_id"], scope=SupportScope.feishu)
        case "Feishu Private":
            return SendTarget(
                data["open_id"],
                private=True,
                scope=SupportScope.feishu,
            )
        case _:
            return None


async def _convert_user_targets() -> None:
    async with get_session() as session:
        users = (await session.scalars(select(User))).all()
        converted = 0
        for user in users:
            # 新格式没有 platform_type，靠它区分
            if "platform_type" not in user.user_target:
                continue
            if not (target := _convert_saa_target(user.user_target)):
                logger.error(
                    f"无法识别的旧发送目标 {user.user_target}，"
                    f"user {user.id} 的订阅将无法推送，请删除后重新订阅"
                )
                continue
            user.user_target = dump_send_target(target)
            converted += 1
        if converted:
            await session.commit()
            logger.success(f"已将 {converted} 个发送目标转换为 uniseg 格式")


async def data_migrate() -> None:
    await _migrate_from_datastore()
    await _convert_user_targets()
