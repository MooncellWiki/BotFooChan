from collections.abc import Awaitable, Callable
import json
from pathlib import Path
from typing import Any

import httpx
from nonebot import logger
from nonebot_plugin_apscheduler import scheduler
import nonebot_plugin_localstore as store

from src.providers.group_binding import group_bindings, resolve_bot

from .data_source import (
    MAINT_ACTION_CN,
    MAINT_ACTION_JP,
    fetch_gamedata_cn,
    fetch_gamedata_jp,
    format_server_time,
    get_action,
    get_detail,
)
from .storage import load_recv_groups

DATA_FILE_CN = store.get_plugin_data_file("gamedata_cn.json")
DATA_FILE_JP = store.get_plugin_data_file("gamedata_jp.json")


def _load_data(file: Path) -> dict[str, Any] | None:
    if not file.exists():
        return None
    try:
        return json.loads(file.read_text("utf-8"))
    except json.JSONDecodeError, OSError:
        return None


def _save_data(file: Path, data: dict[str, Any]) -> None:
    file.write_text(json.dumps(data, ensure_ascii=False), "utf-8")


async def _push_to_groups(text: str) -> None:
    """按群号推送，由 /官q 绑定 登记的官方机器人发；发的是主动消息，占主动推送额度"""
    for group_id in load_recv_groups():
        if (binding := group_bindings.get(str(group_id))) is None:
            logger.warning(
                f"群号 {group_id} 还没绑定官方机器人，跳过维护推送"
                f"（在群里 @ 官方机器人发 /官q 绑定 {group_id}）"
            )
            continue
        if (bot := resolve_bot(binding)) is None:
            logger.warning(f"群号 {group_id} 对应的官方机器人不在线，跳过维护推送")
            continue
        try:
            await bot.send_to_group(binding.group_openid, message=text)
        except Exception as e:
            logger.opt(exception=e).error(f"推送维护状态到群 {group_id} 失败")


async def _check_server(
    name: str,
    fetch: Callable[[], Awaitable[dict[str, Any]]],
    data_file: Path,
    maint_action: str,
) -> None:
    try:
        data = await fetch()
    except (httpx.HTTPError, ValueError) as e:
        logger.opt(exception=e).warning(f"获取 FGO {name}游戏数据失败")
        return

    old_data = _load_data(data_file)
    _save_data(data_file, data)
    if old_data is None:
        return

    is_maint = get_action(data) == maint_action
    was_maint = get_action(old_data) == maint_action
    detail = get_detail(data)
    ts = format_server_time(data)

    if is_maint and not was_maint:
        text = f"{ts}\nFGO{name}维护开始\n维护公告：\n{detail}"
    elif was_maint and not is_maint:
        text = f"{ts}\nFGO{name}维护结束"
    elif is_maint and was_maint and detail != get_detail(old_data):
        text = f"{ts}\nFGO{name}维护公告更新\n维护公告：\n{detail}"
    else:
        return

    await _push_to_groups(text)


@scheduler.scheduled_job("cron", minute="*/5", id="fgo_server_status_cn")
async def check_cn() -> None:
    await _check_server("国服", fetch_gamedata_cn, DATA_FILE_CN, MAINT_ACTION_CN)


@scheduler.scheduled_job("cron", minute="*/5", id="fgo_server_status_jp")
async def check_jp() -> None:
    await _check_server("日服", fetch_gamedata_jp, DATA_FILE_JP, MAINT_ACTION_JP)
