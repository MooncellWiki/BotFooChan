"""把 QQ-GitHub-Bot（Postgres）里的数据导入本项目的 GitHub 插件（SQLite）。

只导三张表：帐号授权（user）、群绑定仓库（group）、事件订阅（subscription）。
Redis 里的都是缓存（消息标记、渲染好的图片等），不用迁。

1. 在旧部署那边把数据导出成一个 JSON 文件（postgres 容器里自带 psql）::

    docker compose exec -T postgres psql -U bot -d bot -At -c "
      SELECT json_build_object(
        'user', (SELECT coalesce(json_agg(t), '[]') FROM \"user\" t),
        'group', (SELECT coalesce(json_agg(t), '[]') FROM \"group\" t),
        'subscription', (SELECT coalesce(json_agg(t), '[]') FROM subscription t)
      )" > qq-github-bot.json

2. 在本项目的容器里导入（会先把数据库升级到最新迁移）::

    docker compose run --rm --no-deps \\
      -v ./qq-github-bot.json:/tmp/qq-github-bot.json \\
      nonebot python scripts/import_qq_github_bot.py /tmp/qq-github-bot.json

可以重复执行：已存在的记录按导入文件覆盖（授权 token、绑定的仓库、订阅的 action），
不会产生重复行。
"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bot  # noqa: F401  —— nonebot.init() + 注册适配器 + 加载插件

# isort: split
# 下面这些在导入时就要用到已初始化的 NoneBot，必须排在 import bot 之后

from nonebot import logger
from nonebot_plugin_orm import get_session
from nonebot_plugin_orm.__main__ import main as orm_main
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from src.plugins.github.models import Group, Subscription, User
from src.providers.platform import GroupInfo, TargetInfo, UserInfo


def _validate[T](adapter: TypeAdapter[T], value: object, what: str) -> T | None:
    try:
        return adapter.validate_python(value)
    except ValidationError:
        logger.warning(f"跳过无法识别的{what}：{value!r}")
        return None


async def import_users(rows: list[dict]) -> int:
    adapter = TypeAdapter(UserInfo)
    count = 0
    for row in rows:
        if (info := _validate(adapter, row["user"], "用户")) is None:
            continue
        await User.create_or_update_by_info(info, access_token=row["access_token"])
        count += 1
    return count


async def import_groups(rows: list[dict]) -> int:
    adapter = TypeAdapter(GroupInfo)
    count = 0
    for row in rows:
        if (info := _validate(adapter, row["group"], "群")) is None:
            continue
        await Group.create_or_update_by_info(info, bind_repo=row["bind_repo"])
        count += 1
    return count


async def import_subscriptions(rows: list[dict]) -> int:
    """原样写入 action：NULL 是订阅全部，[] 是已退订，不能套用订阅时的合并逻辑"""
    adapter = TypeAdapter(TargetInfo)
    count = 0
    async with get_session() as session:
        for row in rows:
            if (info := _validate(adapter, row["subscriber"], "订阅者")) is None:
                continue
            subscriber = info.model_dump()
            existing = await session.scalar(
                select(Subscription).where(
                    Subscription.subscriber == subscriber,
                    Subscription.owner == row["owner"],
                    Subscription.repo == row["repo"],
                    Subscription.event == row["event"],
                )
            )
            if existing is None:
                session.add(
                    Subscription(
                        subscriber=subscriber,
                        owner=row["owner"],
                        repo=row["repo"],
                        event=row["event"],
                        action=row["action"],
                    )
                )
            else:
                existing.action = row["action"]
            count += 1
        await session.commit()
    return count


async def run(dump: dict) -> None:
    users = await import_users(dump.get("user") or [])
    groups = await import_groups(dump.get("group") or [])
    subscriptions = await import_subscriptions(dump.get("subscription") or [])
    logger.success(
        f"导入完成：用户 {users} 个，群 {groups} 个，订阅 {subscriptions} 条"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="把 QQ-GitHub-Bot 的数据导入 GitHub 插件"
    )
    parser.add_argument("dump", type=Path, help="psql 导出的 JSON 文件")
    args = parser.parse_args()

    dump = json.loads(args.dump.read_text(encoding="utf-8"))
    orm_main(["upgrade"], prog_name="orm", standalone_mode=False)
    asyncio.run(run(dump))
