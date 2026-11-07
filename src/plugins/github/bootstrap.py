"""把 QQ 号机器人时代按真实群号存的订阅和仓库绑定转给官方机器人。

QQ 号机器人停用以后，库里 ``qq_group`` 类型的订阅者发不出去（webhook 推送时直接
跳过），官方机器人在群里也查不到绑定的仓库。群号在
:mod:`src.providers.group_binding` 里绑定了官方机器人的，这里改写成官方机器人的
群目标：启动时整理一遍存量，之后新绑定的群号在绑定时当场改。没绑定的群原样留着，
等绑定以后再改。

官方机器人那边已经有同一条记录时（在官方机器人上重新订阅、绑定过）以那边为准，
旧行删掉。已经改过的行不会再动，重复执行没有副作用。

``qq_user`` 的授权不转：QQ 号换不成官方机器人的用户 openid，要在官方机器人上
重新 /install。
"""

from nonebot import get_driver, logger
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from src.providers.group_binding import GroupBinding, group_bindings
from src.providers.platform.targets import QQOfficialGroupInfo, TargetType

from .models import Group, Subscription


def _legacy_group_id(stored: dict) -> str | None:
    """QQ 号机器人时代存的群，返回它的群号"""
    return str(stored["qq_group_id"]) if stored.get("type") == "qq_group" else None


def _official_group(group_id: str) -> dict | None:
    """群号绑定了官方机器人的，换成官方机器人眼里的这个群"""
    if (binding := group_bindings.get(group_id)) is None:
        return None
    return QQOfficialGroupInfo(
        type=TargetType.QQ_OFFICIAL_GROUP, qq_group_open_id=binding.group_openid
    ).model_dump()


async def move_to_official() -> dict[str, int]:
    """改写绑定过的群号，返回这次改成官方机器人的群号及其订阅数"""
    moved: dict[str, int] = {}
    unbound: set[str] = set()

    async with get_session() as session:
        for sub in (await session.scalars(select(Subscription))).all():
            if (group_id := _legacy_group_id(sub.subscriber)) is None:
                continue
            if (official := _official_group(group_id)) is None:
                unbound.add(group_id)
                continue
            existing = await session.scalar(
                select(Subscription).where(
                    Subscription.subscriber == official,
                    Subscription.owner == sub.owner,
                    Subscription.repo == sub.repo,
                    Subscription.event == sub.event,
                )
            )
            if existing is None:
                sub.subscriber = official
            else:
                await session.delete(sub)
            moved[group_id] = moved.get(group_id, 0) + 1

        for group in (await session.scalars(select(Group))).all():
            if (group_id := _legacy_group_id(group.group)) is None:
                continue
            if (official := _official_group(group_id)) is None:
                unbound.add(group_id)
                continue
            existing = await session.scalar(
                select(Group).where(Group.group == official)
            )
            if existing is None:
                group.group = official
            else:
                await session.delete(group)
            moved.setdefault(group_id, 0)

        await session.commit()

    if moved:
        logger.success(f"群号 {'、'.join(moved)} 的 GitHub 订阅改由官方机器人推送")
    if unbound:
        logger.warning(
            f"群号 {'、'.join(sorted(unbound))} 的 GitHub 订阅发不出去，"
            "在群里 @ 官方机器人发 /官q 绑定 <群号> 后改由官方机器人推送"
        )
    return moved


@get_driver().on_startup
async def _startup() -> None:
    await move_to_official()


@group_bindings.on_bind
async def _move_after_bind(group_id: str, binding: GroupBinding) -> str | None:
    """群号刚绑定上官方机器人，这个群号上的订阅当场转过去，不用等重启"""
    if count := (await move_to_official()).get(group_id):
        return f"这个群号上的 {count} 条 GitHub 订阅也改由官方机器人推送了"
    return None
