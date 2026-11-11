"""配置模型里字段的标记，以及按标记处理配置文档。

标记写在字段的 ``json_schema_extra`` 里，会原样出现在 JSON Schema 中，管理后台的
表单据此决定怎么渲染：

- ``secret``：密钥。存库时加密，接口里只给打码后的指纹（见 :func:`mask`）
- ``restart``：只在启动时读一次，改了要重启才生效
- ``model_ref``：模型引用（LLM 注册表里的别名），会出现在「模型路由」页
- ``multiline``：长文本，用多行输入框
- ``prompt``：提示词，会出现在「提示词」页，带修改历史
"""

from collections.abc import Callable
import types
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from . import crypto

Flag = Literal["secret", "restart", "model_ref", "multiline", "prompt"]

MASK = "••••••"
"""打码后的前缀，后面跟密钥指纹"""
ENCRYPTED = "$enc"
"""存库时密钥替换成 {"$enc": "<密文>"}"""


def flags(field: FieldInfo) -> dict[str, Any]:
    extra = field.json_schema_extra
    return extra if isinstance(extra, dict) else {}


def has_flag(field: FieldInfo, flag: Flag) -> bool:
    return bool(flags(field).get(flag))


def flagged(model: type[BaseModel], flag: Flag) -> list[str]:
    """顶层字段里带某个标记的字段名"""
    return [name for name, f in model.model_fields.items() if has_flag(f, flag)]


def _nested(annotation: Any) -> tuple[str, type[BaseModel]] | None:
    """字段类型里嵌套的配置模型：(model | list | dict, 模型类)"""
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        return _nested(args[0]) if len(args) == 1 else None
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return "model", annotation
    args = get_args(annotation)
    if origin in (list, set, tuple, frozenset) and args:
        inner = _nested(args[0])
        return ("list", inner[1]) if inner and inner[0] == "model" else None
    if origin is dict and len(args) == 2:
        inner = _nested(args[1])
        return ("dict", inner[1]) if inner and inner[0] == "model" else None
    return None


def map_secrets(model: type[BaseModel], data: Any, fn: Callable[[Any], Any]) -> Any:
    """对配置文档（``model_dump(mode="json")`` 的结果）里每个非空的密钥值调用 fn"""
    if not isinstance(data, dict):
        return data
    out = dict(data)
    for name, field in model.model_fields.items():
        if name not in out or out[name] in (None, ""):
            continue
        value = out[name]
        if has_flag(field, "secret"):
            out[name] = fn(value)
            continue
        match _nested(field.annotation):
            case ("model", sub):
                out[name] = map_secrets(sub, value, fn)
            case ("list", sub) if isinstance(value, list):
                out[name] = [map_secrets(sub, item, fn) for item in value]
            case ("dict", sub) if isinstance(value, dict):
                out[name] = {k: map_secrets(sub, v, fn) for k, v in value.items()}
            case _:
                pass
    return out


def mask(model: type[BaseModel], data: Any) -> Any:
    """密钥换成「打码前缀 + 指纹」，给接口用"""
    return map_secrets(model, data, lambda v: f"{MASK}{crypto.fingerprint(str(v))}")


def encrypt(model: type[BaseModel], data: Any) -> Any:
    return map_secrets(model, data, lambda v: {ENCRYPTED: crypto.encrypt(str(v))})


def decrypt(model: type[BaseModel], data: Any) -> Any:
    def _one(value: Any) -> Any:
        if isinstance(value, dict) and ENCRYPTED in value:
            return crypto.decrypt(value[ENCRYPTED])
        return value

    return map_secrets(model, data, _one)


class UnknownSecret(ValueError):
    """提交回来的打码值对不上任何原有的密钥"""


def restore(model: type[BaseModel], new: Any, old: Any) -> Any:
    """把 new 里打码的密钥换回原值。

    按指纹而不是按位置找原值：列表里删了一项、调了顺序，剩下的密钥也不会张冠李戴。
    """
    known: dict[str, Any] = {}

    def _collect(value: Any) -> Any:
        known[crypto.fingerprint(str(value))] = value
        return value

    map_secrets(model, old, _collect)

    def _restore(value: Any) -> Any:
        if not (isinstance(value, str) and value.startswith(MASK)):
            return value
        fp = value.removeprefix(MASK)
        if not fp or fp not in known:
            raise UnknownSecret("有个密钥对不上原来的值，请重新填写")
        return known[fp]

    return map_secrets(model, new, _restore)


def diff(old: Any, new: Any, prefix: str = "") -> dict[str, list[Any]]:
    """两份文档的差异：{点分路径: [旧值, 新值]}，dict 逐层展开，其余整体比较"""
    if isinstance(old, dict) and isinstance(new, dict):
        out: dict[str, list[Any]] = {}
        for key in sorted(old.keys() | new.keys()):
            out |= diff(old.get(key), new.get(key), f"{prefix}{key}.")
        return out
    if old != new:
        return {prefix.removesuffix("."): [old, new]}
    return {}
