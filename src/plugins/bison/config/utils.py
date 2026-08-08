from datetime import UTC, datetime
from typing import Any

from nonebot_plugin_alconna.uniseg import Target as SendTarget

NEVER_USED = datetime.fromtimestamp(0, UTC).replace(tzinfo=None)
"""``Cookie.last_usage`` 的初始值，表示这条 cookie 还没被用过"""


def db_now() -> datetime:
    """数据库里存的「当前时间」：UTC，且不带时区

    SQLite 的 DateTime 列存不下时区，写入时 tzinfo 会被静默丢弃、读回来永远是
    naive，所以库里的时间统一按 naive UTC 存。否则写进去的是 aware、读出来是
    naive，``last_usage + cd < now`` 这类比较会抛
    ``can't compare offset-naive and offset-aware datetimes``。
    """
    return datetime.now(UTC).replace(tzinfo=None)


class NoSuchUserException(Exception):
    pass


class NoSuchSubscribeException(Exception):
    pass


class NoSuchTargetException(Exception):
    pass


class DuplicateCookieTargetException(Exception):
    pass


def dump_send_target(target: SendTarget) -> dict[str, Any]:
    """把发送目标序列化成可以放进 ``User.user_target`` 的形式

    ``user_target`` 同时充当订阅者的身份（查询/删除订阅都靠它匹配），所以序列化结果
    必须稳定：``extra`` 里可能带上事件级别的信息（例如 QQ 的 ``qq.reply_seq``），
    每条消息都不一样，留着会让同一个群在库里存成多条 User 记录。

    ``self_id`` 保留：本项目同时接了两个 QQ 官方 bot，而群/私聊的 openid 是按 bot
    区分的，只靠 scope 选 bot 会发错。代价是换 bot 账号后旧订阅在管理命令里会变成
    另一个目标（推送仍然可用，``Target.select`` 找不到 self_id 时会回退到 scope）。
    """
    data = target.dump()
    data["extra"] = {}
    return data


def load_send_target(data: dict[str, Any]) -> SendTarget:
    """``dump_send_target`` 的逆操作

    ``Target.load`` 会 pop 传入的 dict，所以这里始终传副本。
    """
    return SendTarget.load(dict(data))
