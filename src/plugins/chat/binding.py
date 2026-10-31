"""QQ 号机器人（OneBot、Milky）的群号 ↔ QQ 官方机器人 group_openid 的绑定表。

QQ 号机器人侧只认真实群号，官方机器人侧只认脱敏的 group_openid，两边都没有公开
接口能把对方的标识换算过来，所以只能由超管在群内手动登记一次。

group_openid 是按 AppID 分发的（同一个群，换个机器人就是另一串 openid），
因此绑定里连 AppID 一起记下来，多机器人同时在线时才能挑对发送方。

绑定表原先存在 deepseek 插件的数据目录下，插件并入通用对话后改存本插件目录；
新位置还没有文件时从旧位置读一次，下次保存就落到新位置。
"""

import json

from nonebot import logger
from nonebot_plugin_alconna import SupportAdapter
import nonebot_plugin_localstore as store
from pydantic import BaseModel

QQ_CLIENT_ADAPTERS = frozenset({SupportAdapter.onebot11, SupportAdapter.milky})
"""QQ 号机器人的协议端，事件里的群号就是真实群号"""


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
        source = self.file
        if not source.exists():
            source = store.get_data_dir(None) / "deepseek" / self.file.name
            if not source.exists():
                return

        try:
            data = json.loads(source.read_text(encoding="utf-8"))
            self.bindings = {
                str(group_id): GroupBinding.model_validate(binding)
                for group_id, binding in data.items()
            }
        except Exception as e:
            logger.opt(exception=e).error(f"群 markdown 绑定表读取失败：{source}")

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
