"""全局用户记忆 provider。

以用户为粒度记录喜好/忌口（自由文本条目）与所在地区，持久化到 localstore，
供 what2eat 等插件生成个性化内容时引用；由 memory 插件提供管理指令。
"""

from collections.abc import Iterable
import json

from nonebot import logger, require

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store
from pydantic import BaseModel, Field

MAX_PREFERENCES = 30
"""每个用户最多保留的喜好条目数，超出时淘汰最早的记录"""


class UserProfile(BaseModel):
    region: str | None = None
    """所在地区"""
    preferences: list[str] = Field(default_factory=list)
    """喜好/忌口等自由文本条目"""

    @property
    def is_empty(self) -> bool:
        return self.region is None and not self.preferences

    def describe(self) -> str:
        """格式化画像，用于展示与 LLM 提示词"""
        lines = [f"地区：{self.region or '未知'}"]
        if self.preferences:
            lines.append("喜好与忌口：")
            lines.extend(
                f"{index}. {item}"
                for index, item in enumerate(self.preferences, start=1)
            )
        else:
            lines.append("喜好与忌口：暂无记录")
        return "\n".join(lines)


class MemoryStore:
    """基于 localstore JSON 文件的用户记忆存储"""

    def __init__(self) -> None:
        self.file = store.get_data_file("memory", "profiles.json")
        self._profiles: dict[str, UserProfile] = {}
        self._load()

    def _load(self) -> None:
        if not self.file.exists():
            return
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            self._profiles = {
                user_id: UserProfile.model_validate(profile)
                for user_id, profile in data.items()
            }
        except (OSError, ValueError) as e:
            logger.opt(exception=e).error(f"读取用户记忆失败: {self.file}")

    def _save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(
            json.dumps(
                {
                    user_id: profile.model_dump()
                    for user_id, profile in self._profiles.items()
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def get(self, user_id: str) -> UserProfile:
        profile = self._profiles.get(user_id)
        return profile.model_copy(deep=True) if profile else UserProfile()

    def set_region(self, user_id: str, region: str | None) -> None:
        profile = self._profiles.setdefault(user_id, UserProfile())
        profile.region = region.strip() if region and region.strip() else None
        self._save()

    def add_preferences(self, user_id: str, items: Iterable[str]) -> list[str]:
        """记录新的喜好条目，返回实际新增的条目（自动去重）"""
        profile = self._profiles.setdefault(user_id, UserProfile())
        added = []
        for item in items:
            item = item.strip()
            if item and item not in profile.preferences:
                profile.preferences.append(item)
                added.append(item)
        del profile.preferences[:-MAX_PREFERENCES]
        if added:
            self._save()
        return added

    def remove_preferences(self, user_id: str, keywords: Iterable[str]) -> list[str]:
        """删除包含任一关键词的喜好条目，返回被删除的条目"""
        profile = self._profiles.get(user_id)
        if not profile:
            return []
        removed = [
            item
            for item in profile.preferences
            if any(keyword in item for keyword in keywords)
        ]
        if removed:
            profile.preferences = [
                item for item in profile.preferences if item not in removed
            ]
            self._save()
        return removed

    def clear(self, user_id: str) -> bool:
        """清空指定用户的全部记忆"""
        if self._profiles.pop(user_id, None) is None:
            return False
        self._save()
        return True


memory_store = MemoryStore()
