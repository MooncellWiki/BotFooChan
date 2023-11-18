import json
from pathlib import Path

assets_path = Path(__file__).parent / "assets"


def resolve_data(name: str):
    dest = assets_path / name

    return json.loads(dest.read_text(encoding="utf-8"))


main = (
    "本骰娘由 nonebot2 强力驱动\n"
    ".r    投掷指令 todo\n"
    "    d   制定骰子面数\n"
    "    a   检定\n"
    "    h   暗骰\n"
    "    #   多轮检定\n"
    "    bp  奖励骰&惩罚骰\n"
    "    +/- 附加计算  todo\n"
    ".sc   疯狂检定\n"
    ".st   射击命中判定\n"
    ".ti   临时疯狂症状\n"
    ".li   总结疯狂症状\n"
    ".coc  coc角色作成\n"
    ".help 帮助信息\n"
    ".en   技能成长\n"
    ".set  角色卡设定\n"
    ".show 角色卡查询\n"
    ".sa   快速检定\n"
    ".del  删除数据\n"
    "输入.help+指令名获取详细信息"
)
r = (
    ".r[dah#bp] a_number [+/-]ex_number\n"
    "d：骰子设定指令,标准格式为xdy，x为骰子数量y为骰子面数；\n"
    "a：检定指令，根据后续a_number设定数值检定；\n"
    "h：暗骰指令，骰子结构将会私聊发送给该指令者；\n"
    "#：多轮投掷指令，#后接数字即可设定多轮投掷；\n"
    "bp：奖励骰与惩罚骰；\n"
    "+/-：附加计算指令，目前仅支持数字"
)
sc = (
    ".sc success/failure san_number\n"
    "success：判定成功降低san值，支持x或xdy语法（x与y为数字）；\n"
    "failure：判定失败降低san值，支持语法如上；\n"
    "san_number：当前san值，缺省san_number将会自动使用保存的人物卡数据。"
)
set = (
    ".set [attr_name] [attr_num]\n"
    "attr_name：属性名称，例 name、名字、str、力量\n"
    "attr_num：属性值\n"
    "可以单独输入.set指令，骰娘将自动读取最近一次coc指令结果进行保存"
)
show = (
    ".show[s] [@xxx]\n"
    "查看指定调查员保存的人物卡，缺省at则查询自身人物卡\n"
    ".shows 为查看技能指令"
)
sa = ".sa [attr_name]\nattr_name：属性名称，例:name、名字、str、力量"
en = ".en skill_level\nskill_level：需要成长的技能当前等级。"
del_ = (
    ".del [c|card|xxx]\n"
    "删除数据，args可以有以下值\n"
    "c:清空暂存数据\n"
    "card:删除使用中的人物卡(慎用)\n"
    "xxx:其他任意技能名\n"
    "该命令支持多个参数混合使用，可以一次指定多个技能名，使用空格隔开"
)

success_level = {
    0: "大失败",
    1: "失败",
    2: "成功",
    3: "困难成功",
    4: "极难成功",
    5: "大成功",
}

temporary_madness: list[str] = resolve_data("temporary_madness.json")
madness_end: list[str] = resolve_data("madness_end.json")
phobias: list[str] = resolve_data("phobias.json")
manias: list[str] = resolve_data("manias.json")
