"""错误类型，对应 diro crate 的 error.rs。

diro-py 绑定层将除 ZeroDivision 外的所有错误映射为 ValueError，
ZeroDivision 映射为 ZeroDivisionError，此处保持一致：
DiroError 继承 ValueError，除零直接抛出内置 ZeroDivisionError。
"""


class DiroError(ValueError):
    """diro 解析/求值错误基类"""


class ParseError(DiroError):
    """表达式无法解析，对应 PestError"""

    def __init__(self, source: str, pos: int) -> None:
        super().__init__(f"invalid dice expression {source!r} at position {pos}")
        self.source = source
        self.pos = pos


class IntRangeError(DiroError):
    """数值超出对应 Rust 整数类型范围，对应 IntParseError"""

    def __init__(self, value: int, type_name: str) -> None:
        super().__init__(f"number {value} out of range for {type_name}")


class KQTooBigError(DiroError):
    def __init__(self) -> None:
        super().__init__("KQ number can't be bigger than the amount of dices")


class NoDiceError(DiroError):
    def __init__(self) -> None:
        super().__init__("At least one dice must be present")


class DiceNotRolledError(DiroError):
    def __init__(self) -> None:
        super().__init__("Dice should roll before calculate")


U8_MAX = 0xFF
U16_MAX = 0xFFFF
I8_MIN, I8_MAX = -0x80, 0x7F
I32_MIN, I32_MAX = -0x80000000, 0x7FFFFFFF


def check_u8(value: int) -> int:
    if not 0 <= value <= U8_MAX:
        raise IntRangeError(value, "u8")
    return value


def check_u16(value: int) -> int:
    if not 0 <= value <= U16_MAX:
        raise IntRangeError(value, "u16")
    return value


def check_i8(value: int) -> int:
    if not I8_MIN <= value <= I8_MAX:
        raise IntRangeError(value, "i8")
    return value


def check_i32(value: int) -> int:
    if not I32_MIN <= value <= I32_MAX:
        raise IntRangeError(value, "i32")
    return value
