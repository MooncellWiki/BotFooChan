"""从上游 nonebot-bison 插件迁移已有数据，并整理 ``user_target`` 存量格式

上游插件和本插件的表结构完全一致（表名也沿用 ``nonebot_bison_*``），差别只有两处：

1. 上游用 nonebot-plugin-datastore，数据库固定在 ``<datastore 数据目录>/data.db``；
   本插件用 nonebot-plugin-orm，默认库是另一个文件。
2. 上游用 saa 序列化发送目标，本插件用 uniseg 的 ``Target``，``user_target``
   这一列的 JSON 结构不同。

除了 saa 格式，``user_target`` 历史上还有过带 ``adapter``/``platforms`` 字段的旧
uniseg dump（从事件里拿到的）和群管理流程手写的无 adapter 版本。订阅命令按
``user_target`` 匹配订阅者，格式不一致会让同一个群「推送正常但查询/删除是空的」，
还会被存成多条 User。所以启动时统一重写成 ``dump_send_target`` 的规范格式，再把
指向同一会话的重复 User 合并掉。

QQ 号机器人（Milky、OneBot）已经不再使用，按真实群号存的订阅发不出去。群号在
:mod:`src.providers.group_binding` 里绑定了官方机器人的，整理时一并改成官方机器人的
群目标，推送和订阅管理都转到官方机器人；之后新绑定的群号在绑定时当场改（见
``bootstrap``）。没绑定的群照旧按群号存，等绑定以后再改。

所有步骤都是幂等的：库里已经有订阅时不再从旧库搬，``user_target`` 已经是规范格式
时不再改写，已经改成官方机器人的群不会再改。
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
from sqlalchemy.orm import selectinload

from src.providers.group_binding import group_bindings

from .db_model import Cookie, CookieTarget, ScheduleTimeWeight, Subscribe, Target, User
from .utils import dump_send_target, load_send_target, same_send_target

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


def _to_official(target: SendTarget) -> SendTarget | None:
    """群号绑定了官方机器人的 QQ 群，换成官方机器人眼里的这个群

    私聊不换：QQ 号换不成官方机器人的用户 openid。
    """
    if target.scope != SupportScope.qq_client or target.private or target.channel:
        return None
    if (binding := group_bindings.get(target.id)) is None:
        return None
    return SendTarget(
        binding.group_openid, self_id=binding.bot_id, scope=SupportScope.qq_api
    )


async def normalize_user_targets() -> dict[str, int]:
    """整理 ``user_target``，返回这次改成官方机器人的群号及其订阅数"""
    async with get_session() as session:
        users = (
            await session.scalars(select(User).options(selectinload(User.subscribes)))
        ).all()
        converted = 0
        normalized = 0
        moved: dict[str, int] = {}
        unbound: list[str] = []
        valid: list[User] = []
        for user in users:
            data = user.user_target
            # 新格式没有 platform_type，靠它区分
            if "platform_type" in data:
                if not (target := _convert_saa_target(data)):
                    logger.error(
                        f"无法识别的旧发送目标 {data}，"
                        f"user {user.id} 的订阅将无法推送，请删除后重新订阅"
                    )
                    continue
                converted += 1
            else:
                try:
                    target = load_send_target(data)
                except TypeError, ValueError:
                    logger.error(
                        f"无法解析的发送目标 {data}，"
                        f"user {user.id} 的订阅将无法管理，请删除后重新订阅"
                    )
                    continue
            if official := _to_official(target):
                moved[target.id] = moved.get(target.id, 0) + len(user.subscribes)
                target = official
            elif target.scope == SupportScope.qq_client and not target.private:
                unbound.append(target.id)
            canonical = dump_send_target(target)
            if canonical != data:
                user.user_target = canonical
                if not official:
                    normalized += 1
            valid.append(user)

        # 合并指向同一会话的重复 User：不同入口写入的格式不同（有无 self_id 等），
        # 同一个群会被建出多条记录，推送两份、查询却只能看到其中一条
        merged = 0
        kept: list[User] = []
        for user in valid:
            dup = next(
                (
                    k
                    for k in kept
                    if same_send_target(
                        k.user_target, load_send_target(user.user_target)
                    )
                ),
                None,
            )
            if dup is None:
                kept.append(user)
                continue
            keep, drop = dup, user
            # 优先保留带 self_id 的记录，它信息更全，和事件里 dump 出来的一致
            if drop.user_target.get("self_id") and not keep.user_target.get("self_id"):
                kept[kept.index(keep)] = drop
                keep, drop = drop, keep
            subscribed_targets = {sub.target_id for sub in keep.subscribes}
            for sub in list(drop.subscribes):
                if sub.target_id in subscribed_targets:
                    await session.delete(sub)
                else:
                    sub.user = keep
            await session.delete(drop)
            merged += 1

        if converted or normalized or moved or merged:
            await session.commit()
            parts = []
            if converted:
                parts.append(f"saa 格式转换 {converted} 条")
            if normalized:
                parts.append(f"重写为规范格式 {normalized} 条")
            if moved:
                parts.append(f"群号 {'、'.join(moved)} 改由官方机器人推送")
            if merged:
                parts.append(f"合并重复记录 {merged} 条")
            logger.success(f"已整理订阅者数据：{'，'.join(parts)}")
        if unbound:
            logger.warning(
                f"群号 {'、'.join(unbound)} 还按 QQ 号机器人推送，"
                "在群里 @ 官方机器人发 /官q 绑定 <群号> 后改由官方机器人推送"
            )
        return moved


async def data_migrate() -> None:
    await _migrate_from_datastore()
    await normalize_user_targets()
