"""QQ 群号 ↔ QQ 官方机器人 group_openid 的绑定表。

官方机器人只认按 AppID 脱敏的 group_openid，外部推送（OneBot 兼容接口）用的是
真实群号，没有公开接口能换算。所以由超管在群里 @ 官方机器人发 ``/官q 绑定 <群号>``
登记一次（见 :mod:`src.plugins.qq_official`）：群号手填，group_openid 和 AppID
直接取自那条消息。

group_openid 是按 AppID 分发的（同一个群，换个机器人就是另一串 openid），
因此绑定里连 AppID 一起记下来，多机器人同时在线时才能挑对发送方。

绑定表原先放在通用对话插件（更早是 deepseek 插件）的数据目录下，新位置还没有
文件时从旧位置搬过来，旧文件不删。
"""

import json

from nonebot import get_bots, logger, require
from nonebot.adapters.qq import Bot as QQBot
from pydantic import BaseModel

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

LEGACY_PLUGINS = ("chat", "deepseek")
"""绑定表以前所在插件的数据目录，按先后找"""


class GroupBinding(BaseModel):
    group_openid: str
    """官方机器人视角下的群 openid"""
    bot_id: str | None = None
    """官方机器人 AppID，缺省时在已连接的官方机器人里自动挑选（老数据才会缺）"""

    def belongs_to(self, bot_id: str, group_openid: str) -> bool:
        return self.group_openid == group_openid and self.bot_id in (None, bot_id)


class GroupBindingStore:
    """群号 -> 绑定信息，持久化到 localstore"""

    def __init__(self) -> None:
        self.file = store.get_plugin_data_file("group_bindings.json")
        self.bindings: dict[str, GroupBinding] = {}
        self.load()

    def load(self) -> None:
        source = self.file
        if not source.exists():
            legacy = (
                store.get_data_dir(None) / plugin / self.file.name
                for plugin in LEGACY_PLUGINS
            )
            if (source := next((p for p in legacy if p.exists()), None)) is None:
                return

        try:
            data = json.loads(source.read_text(encoding="utf-8"))
            self.bindings = {
                str(group_id): GroupBinding.model_validate(binding)
                for group_id, binding in data.items()
            }
        except Exception as e:
            logger.opt(exception=e).error(f"群号绑定表读取失败：{source}")
            return

        if source != self.file:
            self.save()
            logger.info(f"群号绑定表已从 {source} 搬到 {self.file}")

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(
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
        tmp.replace(self.file)

    def get(self, group_id: str) -> GroupBinding | None:
        return self.bindings.get(str(group_id))

    def find(self, bot_id: str, group_openid: str) -> str | None:
        """官方机器人眼里的这个群绑定的群号"""
        return next(
            (
                group_id
                for group_id, binding in self.bindings.items()
                if binding.belongs_to(bot_id, group_openid)
            ),
            None,
        )

    def bind(self, group_id: str, bot_id: str, group_openid: str) -> None:
        """登记群号；同一个群只留一个群号，原先绑的群号一并去掉"""
        self.bindings = {
            other: binding
            for other, binding in self.bindings.items()
            if not binding.belongs_to(bot_id, group_openid)
        }
        self.bindings[str(group_id)] = GroupBinding(
            group_openid=group_openid, bot_id=bot_id
        )
        self.save()

    def remove(self, group_id: str) -> bool:
        if self.bindings.pop(str(group_id), None) is None:
            return False
        self.save()
        return True


group_bindings = GroupBindingStore()


def get_qq_bots() -> list[QQBot]:
    return [bot for bot in get_bots().values() if isinstance(bot, QQBot)]


def resolve_bot(binding: GroupBinding) -> QQBot | None:
    """挑出该绑定对应的官方机器人。

    绑定里记了 AppID 就按 AppID 找；没记则只在唯一一个官方机器人在线时才敢用，
    多个在线时无从判断 group_openid 属于谁，交由调用方提示重新绑定。
    """
    bots = get_qq_bots()
    if binding.bot_id is not None:
        return next((bot for bot in bots if bot.self_id == binding.bot_id), None)
    return bots[0] if len(bots) == 1 else None
