"""骰子定义与掷骰结算，对应 diro crate 的 dice.rs。

与上游的差异（上游 bug 修正）：
- 上游 D100 的十位取值 0..=8、个位取值 1..=9，导致永远掷不出
  90 以上、100 与整十数；此处修正为十位/个位均取 0..=9，且 00 记为 100。
- 奖励/惩罚骰按最终结果值取优/取劣（而非仅比较十位数字），
  正确处理 00=100 的情况。
- 无限骰/双十字骰的爆炸过程增加总骰数上限，避免恶意表达式
  （如 5a1）导致无限循环。
"""

import random

from .error import (
    DiceNotRolledError,
    DiroError,
    KQTooBigError,
    NoDiceError,
    check_i8,
    check_u8,
    check_u16,
)

MAX_EXPLOSION_DICE = 4096

type _D100Round = tuple[list[int], bool, list[int]]  # ([十位, 个位], 奖励骰?, 附加骰)


def _dhr(tens: int, ones: int) -> int:
    return 100 if tens == 0 and ones == 0 else tens * 10 + ones


class RollResult:
    """掷骰结果，对应 diro::RollResult。

    与 diro-py 绑定一致：``result()`` 与 ``__call__()`` 返回结算值，
    ``detail()`` 返回过程字符串。
    """

    def __init__(self, kind: str, **data) -> None:
        self.kind = kind
        self.d100_rounds: list[_D100Round] = data.get("d100_rounds", [])
        self.kq: int = data.get("kq", 0)
        self.values: list[int] = data.get("values", [])
        self.rounds: list[list[int]] = data.get("rounds", [])
        self.add_line: int = data.get("add_line", 0)
        self.success_line: int = data.get("success_line", 0)
        self.count_line: int = data.get("count_line", 0)

    def detail(self) -> str:
        if self.kind == "d100":
            parts = []
            for digits, is_bonus, bp_digits in self.d100_rounds:
                s = f"{digits[0]}{digits[1]}"
                for d in bp_digits:
                    s += ("B" if is_bonus else "P") + str(d)
                parts.append(s)
            return "+".join(parts)
        elif self.kind == "dice":
            return "+".join(str(v) for v in self.values)
        elif self.kind in ("adice", "cdice"):
            return " ".join(
                f"[{i + 1}]:" + " ".join(str(v) for v in row)
                for i, row in enumerate(self.rounds)
            )
        else:  # fdice
            return "".join(
                "+" if v > 0 else "0" if v == 0 else "-" for v in self.values
            )

    def result(self) -> int:
        if self.kind == "d100":
            total = 0
            for digits, is_bonus, bp_digits in self.d100_rounds:
                tens, ones = digits
                pick = min if is_bonus else max
                total += pick(
                    (_dhr(t, ones) for t in [tens, *bp_digits]),
                    default=_dhr(tens, ones),
                )
            return total
        elif self.kind == "dice":
            if self.kq == 0:
                return sum(self.values)
            elif self.kq > 0:
                return sum(sorted(self.values, reverse=True)[: self.kq])
            else:
                return sum(sorted(self.values)[: -self.kq])
        elif self.kind == "adice":
            return sum(1 for row in self.rounds for v in row if v >= self.success_line)
        elif self.kind == "cdice":
            total = sum(v for row in self.rounds for v in row if v >= self.count_line)
            return total + max(self.rounds[-1])
        else:  # fdice
            return sum(self.values)

    def __call__(self) -> int:
        return self.result()

    def __repr__(self) -> str:
        return f"RollResult({self.detail()}={self.result()})"


class Dice:
    """一枚（组）骰子，对应 diro::Dice 枚举。

    构造签名与 diro-py 绑定一致：``Dice(count=1, face=100, bp=0, kq=0)``。
    """

    def __init__(self, count: int = 1, face: int = 100, bp: int = 0, kq: int = 0):
        self.kind = ""
        self.count = 0
        self.face = 0
        self.bp = 0
        self.kq = 0
        self.add_line = 0
        self.success_line = 0
        self.count_line = 0
        self._init_dice(count, face, bp, kq, 0)

    def _init_dice(self, count: int, face: int, bp: int, kq: int, a: int) -> None:
        """对应 Dice::_dice 的分类逻辑"""
        check_u8(count)
        check_u16(face)
        check_i8(bp)
        check_i8(kq)
        check_u16(a)
        if count == 0:
            raise NoDiceError
        elif a != 0:
            self.kind = "adice"
            self.count = count
            self.face = self._check_face(face)
            self.add_line = face + 1
            self.success_line = a
        elif bp != 0 or face == 100:
            self.kind = "d100"
            self.count = count
            self.bp = bp
        elif abs(kq) <= count:
            self.kind = "dice"
            self.count = count
            self.face = self._check_face(face)
            self.kq = kq
        else:
            raise KQTooBigError

    @staticmethod
    def _check_face(face: int) -> int:
        if face == 0:
            raise DiroError("dice face can't be 0")
        return face

    @classmethod
    def _dice(cls, count: int, face: int, bp: int, kq: int, a: int) -> "Dice":
        dice = cls.__new__(cls)
        Dice.__init__(dice)
        dice._init_dice(count, face, bp, kq, a)
        return dice

    @classmethod
    def d100(cls, count: int, bp: int) -> "Dice":
        return cls._dice(count, 100, bp, 0, 0)

    @classmethod
    def dice(cls, count: int, face: int, kq: int) -> "Dice":
        return cls._dice(count, face, 0, kq, 0)

    @classmethod
    def adice(cls, count: int, face: int, success_line: int, add_line: int) -> "Dice":
        check_u8(count)
        check_u16(face)
        check_u16(success_line)
        check_u16(add_line)
        if count == 0:
            raise NoDiceError
        dice = cls.__new__(cls)
        Dice.__init__(dice)
        dice.kind = "adice"
        dice.count = count
        dice.face = cls._check_face(face)
        dice.add_line = add_line
        dice.success_line = success_line
        return dice

    @classmethod
    def cdice(cls, count: int, face: int, count_line: int) -> "Dice":
        check_u8(count)
        check_u16(face)
        check_u16(count_line)
        if count == 0:
            raise NoDiceError
        dice = cls.__new__(cls)
        Dice.__init__(dice)
        dice.kind = "cdice"
        dice.count = count
        dice.face = cls._check_face(face)
        dice.count_line = count_line
        return dice

    @classmethod
    def fdice(cls, count: int) -> "Dice":
        check_u8(count)
        if count == 0:
            raise NoDiceError
        dice = cls.__new__(cls)
        Dice.__init__(dice)
        dice.kind = "fdice"
        dice.count = count
        return dice

    def roll(self) -> RollResult:
        if self.kind == "d100":
            rounds: list[_D100Round] = []
            for _ in range(self.count):
                digits = [random.randint(0, 9), random.randint(0, 9)]
                bp_digits = [random.randint(0, 9) for _ in range(abs(self.bp))]
                rounds.append((digits, self.bp > 0, bp_digits))
            return RollResult("d100", d100_rounds=rounds)
        elif self.kind == "dice":
            values = [random.randint(1, self.face) for _ in range(self.count)]
            return RollResult("dice", kq=self.kq, values=values)
        elif self.kind in ("adice", "cdice"):
            line = self.add_line if self.kind == "adice" else self.count_line
            rows: list[list[int]] = []
            add = self.count
            total = 0
            while True:
                total += add
                if total > MAX_EXPLOSION_DICE:
                    raise DiroError("too many exploding dice")
                row = [random.randint(1, self.face) for _ in range(add)]
                rows.append(row)
                add = sum(1 for v in row if v >= line)
                if add == 0:
                    break
            if self.kind == "adice":
                return RollResult(
                    "adice",
                    rounds=rows,
                    add_line=self.add_line,
                    success_line=self.success_line,
                )
            return RollResult("cdice", rounds=rows, count_line=self.count_line)
        else:  # fdice
            values = [random.randint(-1, 1) for _ in range(self.count)]
            return RollResult("fdice", values=values)

    def expr(self) -> str:
        if self.kind == "d100":
            s = f"{self.count if self.count > 1 else ''}D100"
            if self.bp > 0:
                s += f"B{self.bp}"
            elif self.bp < 0:
                s += f"P{-self.bp}"
            return s
        elif self.kind == "dice":
            s = f"{self.count}D{self.face}"
            if self.kq > 0:
                s += f"K{self.kq}"
            elif self.kq < 0:
                s += f"Q{-self.kq}"
            return s
        elif self.kind == "adice":
            s = f"{self.count}A{self.add_line}"
            if self.success_line != 8:
                s += f"K{self.success_line}"
            if self.face != 10:
                s += f"M{self.face}"
            return s
        elif self.kind == "cdice":
            return f"{self.count}C{self.count_line}M{self.face}"
        else:
            return f"{self.count}F"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Dice):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        return hash((self.kind, self.count, self.face, self.bp, self.kq))

    def __repr__(self) -> str:
        return self.expr()


__all__ = [
    "MAX_EXPLOSION_DICE",
    "Dice",
    "DiceNotRolledError",
    "RollResult",
]
