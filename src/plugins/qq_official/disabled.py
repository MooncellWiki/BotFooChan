"""按群停用官方机器人的开关表。

插件原名 official_switch，改名后新位置还没有文件时从旧数据目录搬过来，旧文件不删。
"""

from datetime import datetime
import json

from nonebot import logger
import nonebot_plugin_localstore as store

LEGACY_PLUGIN = "official_switch"


class DisabledGroups:
    """官方机器人 AppID -> 停用的 group_openid -> 谁、什么时候关的"""

    def __init__(self) -> None:
        self.file = store.get_plugin_data_file("disabled_groups.json")
        self.groups: dict[str, dict[str, dict[str, str]]] = {}

        source = self.file
        if not source.exists():
            source = store.get_data_dir(None) / LEGACY_PLUGIN / self.file.name
            if not source.exists():
                return
        try:
            self.groups = json.loads(source.read_text(encoding="utf-8"))
        except Exception as e:
            logger.opt(exception=e).error(f"官方机器人开关读取失败：{source}")
            return
        if source != self.file:
            self.save()
            logger.info(f"官方机器人开关已从 {source} 搬到 {self.file}")

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.groups, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self.file)

    def disabled(self, app_id: str, group_openid: str) -> bool:
        return group_openid in self.groups.get(app_id, {})

    def disable(self, app_id: str, group_openid: str, by: str) -> None:
        self.groups.setdefault(app_id, {})[group_openid] = {
            "by": by,
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        self.save()

    def enable(self, app_id: str, group_openid: str) -> None:
        groups = self.groups.get(app_id, {})
        if groups.pop(group_openid, None) is not None:
            if not groups:
                del self.groups[app_id]
            self.save()


disabled_groups = DisabledGroups()
