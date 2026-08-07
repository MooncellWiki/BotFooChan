"""人物卡存储与增删查改，迁移自 nonebot_plugin_cocdicer 的 cards.py。

原插件以 OneBot 事件为键，此处改为适配器无关的
(group_id, user_id) 键；群组标识由 common.py 通过 uniseg Target 计算。
"""

from contextlib import suppress
from pathlib import Path

from nonebot import require
from pydantic import BaseModel, Field

require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as localstore

from . import constant, diro
from .dices import expr
from .investigator import Investigator


def _data_file() -> Path:
    return localstore.get_plugin_data_dir() / "cards.json"


class Cards(BaseModel):
    # group_id -> {user_id -> 人物卡}
    data: dict[str, dict[str, Investigator]] = Field(default_factory=dict)

    def save(self) -> None:
        _data_file().write_text(self.model_dump_json(by_alias=True), encoding="utf-8")

    def load(self) -> None:
        readed = Cards.model_validate_json(_data_file().read_text(encoding="utf-8"))
        self.data = readed.data

    def update(
        self, group_id: str, user_id: str, inv: Investigator, save: bool = True
    ) -> None:
        self.data.setdefault(group_id, {})[user_id] = inv
        if save:
            self.save()

    def get(self, group_id: str, user_id: str) -> Investigator | None:
        return self.data.get(group_id, {}).get(user_id)

    def delete(self, group_id: str, user_id: str, save: bool = True) -> bool:
        if self.get(group_id, user_id) is None:
            return False
        self.data[group_id].pop(user_id)
        if save:
            self.save()
        return True

    def delete_skill(
        self, group_id: str, user_id: str, skill_name: str, save: bool = True
    ) -> bool:
        inv = self.get(group_id, user_id)
        if inv is None or skill_name not in inv.skills:
            return False
        inv.skills.pop(skill_name)
        self.update(group_id, user_id, inv, save=save)
        return True


cards = Cards()
cache_cards = Cards()

with suppress(FileNotFoundError, ValueError):
    cards.load()

attrs_dict: dict[str, list[str]] = {
    "名字": ["name", "名字", "名称"],
    "年龄": ["age", "年龄"],
    "力量": ["str_field", "str", "力量"],
    "体质": ["con", "体质"],
    "体型": ["siz", "体型"],
    "敏捷": ["dex", "敏捷"],
    "外貌": ["app", "外貌"],
    "智力": ["int_field", "int", "智力", "灵感"],
    "意志": ["pow", "意志"],
    "教育": ["edu", "教育"],
    "幸运": ["luc", "幸运"],
    "理智": ["san", "理智"],
}


def set_handler(group_id: str, user_id: str, name: str | None, value: str | None):
    if not name:
        inv = cache_cards.get(group_id, user_id)
        if inv is None:
            return "未找到缓存数据，请先使用coc指令生成角色"
        cards.update(group_id, user_id, inv)
        return "成功从缓存保存人物卡属性：\n" + inv.output()

    inv = cards.get(group_id, user_id)
    if inv is None:
        return "未找到已保存数据，请先使用空白set指令保存角色数据"
    if not value:
        return constant.set

    for attr, alias in attrs_dict.items():
        if name in alias:
            if attr == "名字":
                setattr(inv, alias[0], value)
            else:
                try:
                    setattr(inv, alias[0], int(value))
                except ValueError:
                    return "请输入正整数属性数据"
            cards.save()
            return f"设置调查员{attr}为：{value}"
    try:
        inv.skills[name] = int(value)
    except ValueError:
        return "请输入正整数技能数据"
    cards.save()
    return f"设置调查员{name}技能为：{value}"


def show_handler(
    group_id: str, user_id: str, qid: str | None, skills: bool
) -> list[str]:
    r = []
    if qid is not None:
        inv = cards.get(group_id, qid)
        if inv is not None:
            r.append("查询到人物卡：\n" + inv.output())
            if skills:
                r.append(inv.skills_output())
    elif skills:
        inv = cards.get(group_id, user_id)
        if inv is not None:
            r.append(inv.skills_output())
    else:
        inv = cards.get(group_id, user_id)
        if inv is not None:
            r.append("使用中人物卡：\n" + inv.output())
        inv = cache_cards.get(group_id, user_id)
        if inv is not None:
            r.append("已暂存人物卡：\n" + inv.output())
    if not r:
        r.append("无保存/暂存信息")
    return r


def del_handler(group_id: str, user_id: str, args: tuple[str, ...]) -> list[str]:
    r = []
    for arg in args:
        if not arg:
            continue
        elif arg == "c":
            if cache_cards.delete(group_id, user_id, save=False):
                r.append("已清空暂存人物卡数据")
        elif arg == "card":
            if cards.delete(group_id, user_id):
                r.append("已删除使用中的人物卡！")
        elif cards.delete_skill(group_id, user_id, arg):
            r.append("已删除技能" + arg)
        else:
            r.append("未找到人物卡或技能" + arg)
    if not r:
        r.append(constant.del_)
    return r


def sa_handler(group_id: str, user_id: str, attr: str | None) -> str:
    if not attr:
        return constant.sa
    inv = cards.get(group_id, user_id)
    if inv is None:
        return "请先使用set指令保存人物卡后再使用快速检定功能。"
    for name, alias in attrs_dict.items():
        if attr in alias:
            value = getattr(inv, alias[0])
            if not isinstance(value, int):
                return f"属性{name}无法用于检定。"
            return expr(diro.parse(""), value)
    return f"未找到属性{attr}，请检查输入是否正确。"
