"""diro 骰子表达式库的纯 Python 移植。

上游: https://github.com/abrahum/diro （Rust + PyO3）
接口与 diro-py 绑定保持一致::

    d = diro.parse("3d6k2+1")
    d.roll()
    d.calc()          # -> int
    d.detail_expr()   # -> "(5+3)+1" 之类的过程串
    str(d)            # -> "3D6K2+1"

    diro.Dice().roll()()  # 默认 1D100 直接掷骰取值
"""

from .ast import Closed, DiceAst, DiroAst, DyadicOp, Int, Verb
from .dice import Dice, RollResult
from .error import (
    DiceNotRolledError,
    DiroError,
    IntRangeError,
    KQTooBigError,
    NoDiceError,
    ParseError,
)
from .parser import parse_ast


class Diro:
    """骰子表达式的解析结果，对应 diro-py 的 Diro 类"""

    def __init__(self, ast: DiroAst) -> None:
        self._ast = ast

    @property
    def ast(self) -> DiroAst:
        return self._ast

    def eval(self) -> int:
        """掷骰并计算结果"""
        return self._ast.eval()

    def roll(self) -> None:
        """掷出表达式中所有骰子"""
        self._ast.roll()

    def calc(self) -> int:
        """按最近一次掷骰结果计算表达式"""
        return self._ast.calc()

    def expr(self) -> str:
        """表达式字符串"""
        return self._ast.expr()

    def detail_expr(self) -> str:
        """带掷骰过程的表达式字符串"""
        return self._ast.detail_expr()

    def s_expr(self) -> str:
        """S 表达式字符串"""
        return self._ast.s_expr()

    def __repr__(self) -> str:
        return self._ast.expr()

    __str__ = __repr__


def parse(source: str) -> Diro:
    """解析骰子表达式，对应 diro-py 的 parse 函数"""
    return Diro(parse_ast(source))


__all__ = [
    "Closed",
    "Dice",
    "DiceAst",
    "DiceNotRolledError",
    "Diro",
    "DiroAst",
    "DiroError",
    "DyadicOp",
    "Int",
    "IntRangeError",
    "KQTooBigError",
    "NoDiceError",
    "ParseError",
    "RollResult",
    "Verb",
    "parse",
]
