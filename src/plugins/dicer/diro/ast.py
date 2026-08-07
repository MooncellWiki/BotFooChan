"""表达式 AST，对应 diro crate 的 parse/ast.rs。

与上游的差异（上游 bug 修正）：
- 上游 dyadic_with_priority 仅在右侧算符优先级更低时旋转一层，
  同优先级左结合算符（如 10-2+3、10/2*3）会被错误地按右结合计算；
  此处对左结合算符在同优先级时也递归旋转，幂运算保持右结合。
- 除法/取模遵循 Rust i32 语义（向零截断），除零/模零抛出
  ZeroDivisionError；负数次幂与超出 i32 的结果抛出 DiroError。
"""

import enum

from .dice import Dice, RollResult
from .error import DiceNotRolledError, DiroError, check_i32


class Verb(enum.Enum):
    PLUS = ("+", 1)
    MINUS = ("-", 1)
    TIMES = ("*", 2)
    DIVIDE = ("/", 2)
    MODULO = ("%", 2)
    POWER = ("^", 3)

    @property
    def symbol(self) -> str:
        return self.value[0]

    @property
    def priority(self) -> int:
        return self.value[1]

    def __str__(self) -> str:
        return self.symbol


def _trunc_div(lhs: int, rhs: int) -> int:
    q = abs(lhs) // abs(rhs)
    return q if (lhs >= 0) == (rhs >= 0) else -q


def _child_root(root: bool | None) -> bool | None:
    return None if root is None else False


class DiroAst:
    """AST 节点基类，对应 diro::DiroAst"""

    def eval(self) -> int:
        self.roll()
        return self.calc()

    def roll(self) -> None:
        raise NotImplementedError

    def calc(self) -> int:
        raise NotImplementedError

    def expr(self) -> str:
        return self.expr_with_priority(1, None)

    def detail_expr(self) -> str:
        return self.expr_with_priority(1, True)

    def expr_with_priority(self, priority: int, root: bool | None) -> str:
        raise NotImplementedError

    def s_expr(self) -> str:
        raise NotImplementedError

    def __repr__(self) -> str:
        return self.expr()

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return self.__dict__ == other.__dict__

    __hash__ = None  # pyright: ignore[reportAssignmentType]


class Int(DiroAst):
    def __init__(self, value: int) -> None:
        self.value = check_i32(value)

    def roll(self) -> None:
        pass

    def calc(self) -> int:
        return self.value

    def expr_with_priority(self, priority: int, root: bool | None) -> str:
        return str(self.value)

    def s_expr(self) -> str:
        return str(self.value)


class DiceAst(DiroAst):
    """对应 DiroAst::Dice(Dice, Option<RollResult>)"""

    def __init__(self, dice: Dice, result: RollResult | None = None) -> None:
        self.dice = dice
        self.result: RollResult | None = result

    def roll(self) -> None:
        self.result = self.dice.roll()

    def calc(self) -> int:
        if self.result is None:
            raise DiceNotRolledError
        return self.result.result()

    def expr_with_priority(self, priority: int, root: bool | None) -> str:
        if root is None:
            return self.dice.expr()
        if self.result is None:
            raise DiceNotRolledError
        return self.result.detail() if root else str(self.result.result())

    def s_expr(self) -> str:
        return self.dice.expr()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DiceAst):
            return NotImplemented
        return self.dice == other.dice and self.result == other.result


class DyadicOp(DiroAst):
    def __init__(self, verb: Verb, lhs: DiroAst, rhs: DiroAst) -> None:
        self.verb = verb
        self.lhs = lhs
        self.rhs = rhs

    def roll(self) -> None:
        self.lhs.roll()
        self.rhs.roll()

    def calc(self) -> int:
        left, right = self.lhs.calc(), self.rhs.calc()
        if self.verb is Verb.PLUS:
            result = left + right
        elif self.verb is Verb.MINUS:
            result = left - right
        elif self.verb is Verb.TIMES:
            result = left * right
        elif self.verb is Verb.DIVIDE:
            if right == 0:
                raise ZeroDivisionError("division by zero")
            result = _trunc_div(left, right)
        elif self.verb is Verb.MODULO:
            if right == 0:
                raise ZeroDivisionError("modulo by zero")
            result = left - _trunc_div(left, right) * right
        else:  # POWER
            if right < 0:
                raise DiroError("negative power is not supported")
            if right > 31 and abs(left) > 1:
                raise DiroError("power result overflow")
            result = left**right
        return check_i32(result)

    def expr_with_priority(self, priority: int, root: bool | None) -> str:
        child = _child_root(root)
        return (
            f"{self.lhs.expr_with_priority(self.verb.priority, child)}"
            f"{self.verb}"
            f"{self.rhs.expr_with_priority(self.verb.priority, child)}"
        )

    def s_expr(self) -> str:
        return f"({self.verb} {self.lhs.s_expr()} {self.rhs.s_expr()})"


class Closed(DiroAst):
    """括号表达式，对应 DiroAst::Closed"""

    def __init__(self, inner: DiroAst) -> None:
        self.inner = inner

    def roll(self) -> None:
        self.inner.roll()

    def calc(self) -> int:
        return self.inner.calc()

    def expr_with_priority(self, priority: int, root: bool | None) -> str:
        child = _child_root(root)
        if isinstance(self.inner, DyadicOp) and self.inner.verb.priority < priority:
            return f"({self.inner.expr_with_priority(priority, child)})"
        return self.inner.expr_with_priority(priority, child)

    def s_expr(self) -> str:
        return self.inner.s_expr()


def dyadic_with_priority(verb: Verb, lhs: DiroAst, rhs: DiroAst) -> DiroAst:
    """右递归解析结果按算符优先级/结合性重排，对应 DiroAst::dyadic_with_priority"""
    if isinstance(rhs, DyadicOp) and (
        verb.priority > rhs.verb.priority
        or (verb.priority == rhs.verb.priority and verb is not Verb.POWER)
    ):
        return DyadicOp(rhs.verb, dyadic_with_priority(verb, lhs, rhs.lhs), rhs.rhs)
    return DyadicOp(verb, lhs, rhs)


__all__ = [
    "Closed",
    "DiceAst",
    "DiroAst",
    "DyadicOp",
    "Int",
    "Verb",
    "dyadic_with_priority",
]
