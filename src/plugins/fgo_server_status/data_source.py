import base64
from datetime import datetime
import json
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .config import plugin_config

MAINT_ACTION_CN = "maintain"
MAINT_ACTION_JP = "maint"

TZ = ZoneInfo("Asia/Shanghai")


async def fetch_gamedata_cn() -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(plugin_config.fgo_data_url_cn, timeout=30)
    resp.raise_for_status()

    result = resp.text.replace("%3D", "")
    if missing_padding := len(result) % 4:
        result += "=" * (4 - missing_padding)
    return json.loads(base64.b64decode(result))


async def fetch_gamedata_jp() -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(plugin_config.fgo_data_url_jp, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _get_fail(data: dict[str, Any]) -> dict[str, Any]:
    try:
        fail = data["response"][0]["fail"]
    except (KeyError, IndexError, TypeError):
        return {}
    return fail if isinstance(fail, dict) else {}


def get_action(data: dict[str, Any]) -> str | None:
    return _get_fail(data).get("action")


def get_title(data: dict[str, Any]) -> str:
    return _get_fail(data).get("title", "")


def get_detail(data: dict[str, Any]) -> str:
    return _get_fail(data).get("detail", "")


def format_server_time(data: dict[str, Any]) -> str:
    server_time = data.get("cache", {}).get("serverTime")
    dt = (
        datetime.fromtimestamp(server_time, TZ)
        if isinstance(server_time, int | float)
        else datetime.now(TZ)
    )
    return dt.strftime("%Y-%m-%d %H:%M:%S")
