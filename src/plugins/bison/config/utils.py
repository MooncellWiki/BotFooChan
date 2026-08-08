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
    """把发送目标序列化成可以放进 ``User.user_target`` 的规范形式

    ``user_target`` 同时充当订阅者的身份（查询/删除订阅都靠它匹配），所以序列化结果
    必须稳定：

    - ``extra`` 里可能带上事件级别的信息（例如 QQ 的 ``qq.reply_seq``），每条消息都
      不一样，直接清空；
    - ``adapter``/``platforms`` 用 ``only_scope=True`` 统一不存：只有从事件 dump
      出来的目标带这两个字段，手动构造（群管理流程）和从 saa 迁移来的都没有，
      存了反而让同一个群出现多种序列化结果；发送时靠 scope/self_id 选 bot 已经足够。
    - ``self_id`` 保留：本项目同时接了两个 QQ 官方 bot，而群/私聊的 openid 是按 bot
      区分的，只靠 scope 选 bot 会发错。代价是换 bot 账号后旧订阅在管理命令里会变成
      另一个目标（推送仍然可用，``Target.select`` 找不到 self_id 时会回退到 scope）。
    """
    data = target.dump(only_scope=True)
    data["extra"] = {}
    return data


def load_send_target(data: dict[str, Any]) -> SendTarget:
    """``dump_send_target`` 的逆操作

    ``Target.load`` 会 pop 传入的 dict，所以这里始终传副本。
    """
    return SendTarget.load(dict(data))


def same_send_target(stored: dict[str, Any], target: SendTarget) -> bool:
    """判断库里存的发送目标和 ``target`` 是否指向同一个会话

    历史数据里 ``self_id``、``adapter`` 等字段不一定齐全（从 saa 迁移来的没有
    self_id，群管理流程存的没有 adapter），不能按序列化结果全等比较。
    ``Target.verify`` 恰好把缺失字段当通配符处理；它不比较 scope，这里补上：
    两边都有 scope 且不同时视为不同会话（防止不同平台恰好撞了同一个 id）。

    库里可能残留无法识别的旧格式（启动整理时会逐条报错跳过），解析不了的一律
    视为不匹配，别让一条脏数据炸掉整个订阅命令。
    """
    try:
        loaded = load_send_target(stored)
    except TypeError, ValueError:
        return False
    if loaded.scope and target.scope and loaded.scope != target.scope:
        return False
    return loaded.verify(target)
