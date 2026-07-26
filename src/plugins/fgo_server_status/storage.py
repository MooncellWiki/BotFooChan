import json

import nonebot_plugin_localstore as store

RECV_GROUPS_FILE = store.get_plugin_data_file("recv_groups.json")


def load_recv_groups() -> list[int]:
    if not RECV_GROUPS_FILE.exists():
        return []
    try:
        groups = json.loads(RECV_GROUPS_FILE.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [int(group) for group in groups] if isinstance(groups, list) else []


def save_recv_groups(groups: list[int]) -> None:
    RECV_GROUPS_FILE.write_text(json.dumps(groups), "utf-8")
