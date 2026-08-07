"""COC 调查员角色卡，迁移自 nonebot_plugin_cocdicer 的 investigator.py"""

import random

from pydantic import BaseModel, ConfigDict, Field, model_validator

build_dict = {64: -2, 84: -1, 124: 0, 164: 1, 204: 2, 284: 3, 364: 4, 444: 5, 524: 6}
db_dict = {
    -2: "-2",
    -1: "-1",
    0: "0",
    1: "1d4",
    2: "1d6",
    3: "2d6",
    4: "3d6",
    5: "4d6",
    6: "5d6",
}


def randattr(time: int = 3, ex: int = 0) -> int:
    r = sum(random.randint(1, 6) for _ in range(time))
    return (r + ex) * 5


class Investigator(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = "佚名调查员"
    age: int = 20
    str_field: int = Field(default_factory=randattr, alias="str")
    con: int = Field(default_factory=randattr)
    siz: int = Field(default_factory=lambda: randattr(2, 6))
    dex: int = Field(default_factory=randattr)
    app: int = Field(default_factory=randattr)
    int_field: int = Field(default_factory=lambda: randattr(2, 6), alias="int")
    pow: int = Field(default_factory=randattr)
    edu: int = Field(default_factory=lambda: randattr(2, 6))
    luc: int = Field(default_factory=randattr)
    san: int = -1  # 缺省时取意志值，见下方校验器
    skills: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _default_san(self):
        if self.san < 0:
            self.san = self.pow
        return self

    def body_build(self) -> int:
        build = self.str_field + self.con
        for i, j in build_dict.items():
            if build <= i:
                return j
        return 0

    def db(self) -> str:
        return db_dict[self.body_build()]

    def lp_max(self) -> int:
        return (self.con + self.siz) // 10

    def mov(self) -> int:
        r = 8
        if self.age >= 80:
            r -= 5
        elif self.age >= 70:
            r -= 4
        elif self.age >= 60:
            r -= 3
        elif self.age >= 50:
            r -= 2
        elif self.age >= 40:
            r -= 1
        if self.str_field < self.siz and self.dex < self.siz:
            return r - 1
        elif self.str_field > self.siz and self.dex > self.siz:
            return r + 1
        else:
            return r

    def edu_up(self) -> str:
        edu_check = random.randint(1, 100)
        if edu_check <= self.edu:
            return f"教育成长检定D100={edu_check}，小于{self.edu}，无增长。"
        edu_en = random.randint(1, 10)
        self.edu += edu_en
        if self.edu > 99:
            self.edu = 99
            return (
                f"教育成长检定D100={edu_check}，成长1D10={edu_en}，成长到了最高值99！"
            )
        return f"教育成长检定D100={edu_check}，成长1D10={edu_en}，成长到了{self.edu}"

    def edu_ups(self, times: int) -> str:
        return "".join(self.edu_up() for _ in range(times))

    def sum_down(self, total: int) -> None:
        """力量、体质、敏捷合计降低 total 点，各属性下限 15"""
        if self.str_field + self.con + self.dex - 45 < total:
            self.str_field = 15
            self.con = 15
            self.dex = 15
            return
        str_lost = random.randint(0, min(total, self.str_field - 15))
        while total - str_lost > self.con + self.dex - 30:
            str_lost = random.randint(0, min(total, self.str_field - 15))
        self.str_field -= str_lost
        total -= str_lost
        con_lost = random.randint(0, min(total, self.con - 15))
        while total - con_lost > self.dex - 15:
            con_lost = random.randint(0, min(total, self.con - 15))
        self.con -= con_lost
        total -= con_lost
        self.dex -= total

    def age_change(self, age: int = 20) -> str:
        if self.age != 20:
            return ""  # 防止多次年龄增强判定
        if age < 15:
            return "年龄过小，无法担当调查员"
        elif age >= 90:
            return "该调查员已经作古。"
        self.age = age
        if 15 <= age < 20:
            self.str_field -= 5
            self.siz -= 5
            self.edu -= 5
            luc = randattr()
            self.luc = luc if luc > self.luc else self.luc
            return "力量、体型、教育值-5，幸运增强判定一次"
        elif age < 40:
            self.edu_up()
            return "教育增强判定一次"
        elif age < 50:
            self.app -= 5
            self.sum_down(5)
            self.edu_ups(2)
            return "外貌-5，力量、体型、敏捷合计降低5，教育增强判定两次"
        elif age < 60:
            self.app -= 10
            self.sum_down(10)
            self.edu_ups(3)
            return "外貌-10，力量、体型、敏捷合计降低10，教育增强判定三次"
        elif age < 70:
            self.app -= 15
            self.sum_down(20)
            self.edu_ups(4)
            return "外貌-15，力量、体型、敏捷合计降低20，教育增强判定四次"
        elif age < 80:
            self.app -= 20
            self.sum_down(40)
            self.edu_ups(4)
            return "外貌-20，力量、体型、敏捷合计降低40，教育增强判定四次"
        else:
            self.app -= 25
            self.sum_down(80)
            self.edu_ups(4)
            return "外貌-25，力量、体型、敏捷合计降低80，教育增强判定四次"

    def output(self) -> str:
        return (
            f"{self.name} 年龄:{self.age}\n"
            f"力量:{self.str_field} 体质:{self.con} 体型:{self.siz}\n"
            f"敏捷:{self.dex} 外貌:{self.app} 智力:{self.int_field}\n"
            f"意志:{self.pow} 教育:{self.edu} 幸运:{self.luc}\n"
            f"DB:{self.db()} 生命值:{self.lp_max()} "
            f"移动速度:{self.mov()} SAN:{self.san}"
        )

    def skills_output(self) -> str:
        if not self.skills:
            return f"{self.name}当前无任何技能数据。"
        return f"{self.name}技能数据:" + "".join(
            f"\n{k}:{v}" for k, v in self.skills.items()
        )
