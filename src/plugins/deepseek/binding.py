"""OneBot 群号 ↔ QQ 官方机器人 group_openid 的绑定表。

OneBot 侧只认真实群号，官方机器人侧只认脱敏的 group_openid，两边都没有公开
接口能把对方的标识换算过来，所以只能由超管在群内手动登记一次。

group_openid 是按 AppID 分发的（同一个群，换个机器人就是另一串 openid），
因此绑定里连 AppID 一起记下来，多机器人同时在线时才能挑对发送方。
"""

import json

from nonebot import logger
import nonebot_plugin_localstore as store
from pydantic import BaseModel


class GroupBinding(BaseModel):
    group_openid: str
    """官方机器人视角下的群 openid"""
    bot_id: str | None = None
    """官方机器人 AppID，缺省时在已连接的官方机器人里自动挑选"""


class GroupBindingStore:
    """群号 -> 绑定信息，持久化到 localstore"""

    def __init__(self) -> None:
        self.file = store.get_plugin_data_file("group_bindings.json")
        self.bindings: dict[str, GroupBinding] = {}
        self.load()

    def load(self) -> None:
        if not self.file.exists():
            return

        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            self.bindings = {
                str(group_id): GroupBinding.model_validate(binding)
                for group_id, binding in data.items()
            }
        except Exception as e:
            logger.opt(exception=e).error(f"群 markdown 绑定表读取失败：{self.file}")

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(
            json.dumps(
                {
                    group_id: binding.model_dump()
                    for group_id, binding in self.bindings.items()
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def get(self, group_id: str) -> GroupBinding | None:
        return self.bindings.get(str(group_id))

    def set(self, group_id: str, binding: GroupBinding) -> None:
        self.bindings[str(group_id)] = binding
        self.save()

    def remove(self, group_id: str) -> bool:
        if self.bindings.pop(str(group_id), None) is None:
            return False
        self.save()
        return True


group_bindings = GroupBindingStore()
