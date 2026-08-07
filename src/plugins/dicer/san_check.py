"""San Check，迁移自 nonebot_plugin_cocdicer 的 san_check.py"""

from . import constant, diro
from .cards import cards
from .investigator import Investigator


def sc(sf: str | None, san: int | None, group_id: str, user_id: str) -> str:
    """理智检定。

    sf: "成功损失/失败损失"，支持骰子表达式，如 "1/1d6"；
    san: 指定当前 san 值，缺省时使用保存的人物卡。
    """
    try:
        assert sf is not None
        s_and_f = sf.split("/")
        success = diro.parse(s_and_f[0]).eval()
        failure = diro.parse(s_and_f[1]).eval()
    except ValueError, AssertionError, IndexError, ZeroDivisionError:
        return constant.sc

    if san is not None:
        card = Investigator.model_validate({"san": san, "name": "该调查员"})
        using_card = False
    else:
        card = cards.get(group_id, user_id)
        using_card = True
        if card is None:
            return "未找到使用中的人物卡，请使用set指令保存人物卡后再进行理智检查。"

    r = diro.Dice().roll()()
    s = f"San Check:{r}\n"
    down = success if r <= card.san else failure
    s += f"理智降低了{down}点"
    if down >= card.san:
        s += f"\n{card.name}陷入了永久性疯狂"
    elif down >= card.san // 5:
        s += f"\n{card.name}陷入了不定性疯狂"
    elif down >= 5:
        s += f"\n{card.name}陷入了临时性疯狂"
    if using_card:
        card.san = max(card.san - down, 0)
        cards.update(group_id, user_id, card)
    return s
