"""骰子表达式解析器，对应 diro crate 的 parse/mod.rs 与 parse/diro.pest。

按 pest 文法手写的递归下降解析器（PEG 有序选择 + 回溯）：

    main        = SOI ~ expr? ~ EOI
    expr        = dyadic_expr | term
    dyadic_expr = term ~ verb ~ expr
    term        = dice | adice | cdice | fdice | int | "(" ~ expr ~ ")"
    verb        = "+" | "-" | "*" | "/" | "^" | "%" | ^"x"
    dice        = base_dice ~ (b|p|k|q)* ~ a?
    base_dice   = uint? ~ ^"d" ~ uint?          （原子规则，内部不允许空格）
    adice       = uint ~ ^"a" ~ uint ~ k? ~ m?  （无限骰）
    cdice       = uint ~ ^"c" ~ uint ~ m?       （双十字骰）
    fdice       = uint ~ ^"f"                   （Fate 骰）

数值范围与上游一致：骰数 u8、面数 u16、奖惩/取舍 i8、整数 i32，
超出范围抛出 IntRangeError（对应上游 IntParseError）。
"""

from .ast import Closed, DiceAst, DiroAst, Verb, dyadic_with_priority
from .ast import Int as IntAst
from .dice import Dice
from .error import ParseError, check_i8, check_i32, check_u8, check_u16

_VERBS = {
    "+": Verb.PLUS,
    "-": Verb.MINUS,
    "*": Verb.TIMES,
    "x": Verb.TIMES,
    "X": Verb.TIMES,
    "/": Verb.DIVIDE,
    "%": Verb.MODULO,
    "^": Verb.POWER,
}

_OPEN_PARENS = "(（"
_CLOSE_PARENS = ")）"


class _Parser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.pos = 0

    # ------------------------------------------------------------- 基础工具

    def _eof(self) -> bool:
        return self.pos >= len(self.source)

    def _peek(self) -> str:
        return "" if self._eof() else self.source[self.pos]

    def _ws(self) -> None:
        """WHITESPACE = _{ " " }，仅在非原子规则的元素之间生效"""
        while self._peek() == " ":
            self.pos += 1

    def _uint(self) -> int | None:
        start = self.pos
        while self._peek().isdigit():
            self.pos += 1
        if self.pos == start:
            return None
        return int(self.source[start : self.pos])

    def _match_ci(self, letters: str) -> bool:
        ch = self._peek()
        if ch and ch.lower() in letters:
            self.pos += 1
            return True
        return False

    # ------------------------------------------------------------- 文法规则

    def parse(self) -> DiroAst:
        self._ws()
        if self._eof():
            return DiceAst(Dice())
        ast = self._expr()
        self._ws()
        if ast is None or not self._eof():
            raise ParseError(self.source, self.pos)
        return ast

    def _expr(self) -> DiroAst | None:
        lhs = self._term()
        if lhs is None:
            return None
        save = self.pos
        self._ws()
        verb = _VERBS.get(self._peek())
        if verb is not None:
            self.pos += 1
            self._ws()
            rhs = self._expr()
            if rhs is not None:
                return dyadic_with_priority(verb, lhs, rhs)
        self.pos = save
        return lhs

    def _term(self) -> DiroAst | None:
        self._ws()
        for rule in (self._dice, self._adice, self._cdice, self._fdice, self._int):
            node = rule()
            if node is not None:
                return node
        return self._paren()

    def _dice(self) -> DiroAst | None:
        save = self.pos
        base = self._base_dice()
        if base is None:
            self.pos = save
            return None
        count, face = base
        bp = kq = a = 0
        while True:  # extra = b | p | k | q
            mark = self.pos
            self._ws()
            ch = self._peek().lower()
            if not ch or ch not in "bpkq":
                self.pos = mark
                break
            self.pos += 1
            num = self._uint()
            value = check_i8(num) if num is not None else 1
            if ch == "b":
                bp += value
            elif ch == "p":
                bp -= value
            elif ch == "k":
                kq += value
            else:
                kq -= value
        mark = self.pos  # a = ^"a" ~ uint
        self._ws()
        if self._match_ci("a"):
            num = self._uint()
            if num is None:
                self.pos = mark
            else:
                a = check_u16(num)
        else:
            self.pos = mark
        return DiceAst(Dice._dice(count, face, bp, kq, a))

    def _base_dice(self) -> tuple[int, int] | None:
        save = self.pos
        count = self._uint()
        if not self._match_ci("d"):
            self.pos = save
            return None
        face = self._uint()
        return (
            check_u8(count) if count is not None else 1,
            check_u16(face) if face is not None else 100,
        )

    def _adice(self) -> DiroAst | None:
        save = self.pos
        count = self._uint()
        if count is None or not self._match_ci("a"):
            self.pos = save
            return None
        add_line = self._uint()
        if add_line is None:
            self.pos = save
            return None
        success_line, face = 8, 10
        if self._match_ci("k"):  # k = ^"k" ~ uint?
            num = self._uint()
            if num is not None:
                success_line = check_u16(num)
        if self._match_ci("m"):  # m = ^"m" ~ uint?
            num = self._uint()
            if num is not None:
                face = check_u16(num)
        return DiceAst(
            Dice.adice(check_u8(count), face, success_line, check_u16(add_line))
        )

    def _cdice(self) -> DiroAst | None:
        save = self.pos
        count = self._uint()
        if count is None or not self._match_ci("c"):
            self.pos = save
            return None
        count_line = self._uint()
        if count_line is None:
            self.pos = save
            return None
        face = 10
        if self._match_ci("m"):
            num = self._uint()
            if num is not None:
                face = check_u16(num)
        return DiceAst(Dice.cdice(check_u8(count), face, check_u16(count_line)))

    def _fdice(self) -> DiroAst | None:
        save = self.pos
        count = self._uint()
        if count is None or not self._match_ci("f"):
            self.pos = save
            return None
        return DiceAst(Dice.fdice(check_u8(count)))

    def _int(self) -> DiroAst | None:
        save = self.pos
        negative = False
        if self._peek() == "-":
            self.pos += 1
            negative = True
        num = self._uint()
        if num is None:
            self.pos = save
            return None
        return IntAst(check_i32(-num if negative else num))

    def _paren(self) -> DiroAst | None:
        save = self.pos
        if not self._peek() or self._peek() not in _OPEN_PARENS:
            return None
        self.pos += 1
        inner = self._expr()
        if inner is None:
            self.pos = save
            return None
        self._ws()
        if not self._peek() or self._peek() not in _CLOSE_PARENS:
            self.pos = save
            return None
        self.pos += 1
        return Closed(inner)


def parse_ast(source: str) -> DiroAst:
    """解析骰子表达式为 AST，对应 diro::parse；空表达式返回默认 D100"""
    return _Parser(source).parse()


__all__ = ["parse_ast"]
