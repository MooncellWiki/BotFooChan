"""同群关系：从回显里认出来，落到 localstore。

两个机器人在同一个群里时，一方发的话另一方会当成普通群成员的消息收到。拿「刚发出去
的原话」去对另一边刚收到的消息，对上了就知道：

- 官方机器人收到的：这个 group_openid 就是那个群号，发消息的 member_openid 是
  QQ 号机器人
- QQ 号机器人收到的：这个群号就是那个 group_openid，发消息的 QQ 号是官方机器人

只认机器人回复某条消息时发的（见 :func:`record_sent` 的调用方）：订阅推送这类定时
发的消息，群里别的机器人很可能同时在推一模一样的内容，拿来认人会认错。
"""

from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Literal

from nonebot import logger
from pydantic import BaseModel

Side = Literal["client", "official"]
"""client：QQ 号机器人（Milky、OneBot），official：QQ 官方机器人"""

ECHO_WINDOW = 20.0
"""发出去之后多久之内在另一边收到原话，才算这条的回显（秒）"""
MIN_TEXT = 6
"""太短的话（「好的」「收到」）谁都会说，不拿来认人"""
LONG_TEXT = 20
"""这么长的原话碰巧撞上几乎不可能，对上一次就算数；短一些的要对上两次"""
CONFIRMED = 2


def normalize(text: str) -> str:
    """去掉所有空白：@ 前后的空格、换行，两边转出来不一样"""
    return "".join(text.split())


def _weight(text: str) -> int:
    return CONFIRMED if len(text) >= LONG_TEXT else 1


@dataclass(frozen=True)
class Sent:
    side: Side
    self_id: str
    group: str
    """client 侧是群号，official 侧是 group_openid"""
    text: str
    at: float


class SharedGroup(BaseModel):
    """一个两边机器人都在的群"""

    group_openid: str
    app_id: str
    """官方机器人的 AppID：group_openid 按 AppID 分发，换个官方机器人就是另一串"""
    group_id: int
    client_id: str
    """QQ 号机器人的 QQ 号"""
    member_openid: str | None = None
    """QQ 号机器人在官方机器人眼里的 member_openid，官方机器人收到过它的回显才知道"""
    score: int = 0

    @property
    def confirmed(self) -> bool:
        return self.score >= CONFIRMED


class OfficialAccount(BaseModel):
    """官方机器人在 QQ 号机器人眼里的 QQ 号"""

    uin: str
    app_id: str
    score: int = 0

    @property
    def confirmed(self) -> bool:
        return self.score >= CONFIRMED


class SharedGroupStore:
    def __init__(self, file: Path) -> None:
        self.file = file
        self.groups: dict[str, SharedGroup] = {}
        """group_openid -> 同群关系"""
        self.officials: dict[str, OfficialAccount] = {}
        """官方机器人的 QQ 号 -> 账号"""
        self._sent: deque[Sent] = deque(maxlen=256)
        self.load()

    def load(self) -> None:
        if not self.file.exists():
            return
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            self.groups = {
                openid: SharedGroup.model_validate(group)
                for openid, group in data.get("groups", {}).items()
            }
            self.officials = {
                uin: OfficialAccount.model_validate(account)
                for uin, account in data.get("officials", {}).items()
            }
        except Exception as e:
            logger.opt(exception=e).error(f"同群关系读取失败：{self.file}")

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "groups": {k: v.model_dump() for k, v in self.groups.items()},
            "officials": {k: v.model_dump() for k, v in self.officials.items()},
        }
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self.file)

    # region 查询

    def shared(self, group_openid: str) -> SharedGroup | None:
        group = self.groups.get(group_openid)
        return group if group is not None and group.confirmed else None

    def shared_by_group_id(self, group_id: int) -> list[SharedGroup]:
        return [
            group
            for group in self.groups.values()
            if group.confirmed and group.group_id == group_id
        ]

    def official(self, uin: str) -> OfficialAccount | None:
        account = self.officials.get(uin)
        return account if account is not None and account.confirmed else None

    # region 学习

    def record_sent(
        self, side: Side, self_id: str, group: str, text: str, now: float | None = None
    ) -> None:
        if len(text := normalize(text)) >= MIN_TEXT:
            self._sent.append(
                Sent(
                    side, self_id, group, text, time.monotonic() if now is None else now
                )
            )

    def _echo_of(self, side: Side, text: str, now: float | None) -> Sent | None:
        """在 ``side`` 这边收到的 ``text`` 是不是另一边刚发的；发到了好几个群就认不出"""
        if len(text := normalize(text)) < MIN_TEXT:
            return None
        now = time.monotonic() if now is None else now
        matches = {
            (sent.self_id, sent.group): sent
            for sent in self._sent
            if sent.side != side
            and sent.text == text
            and 0 <= now - sent.at <= ECHO_WINDOW
        }
        return next(iter(matches.values())) if len(matches) == 1 else None

    def observe_official(
        self,
        app_id: str,
        group_openid: str,
        member_openid: str,
        text: str,
        now: float | None = None,
    ) -> bool:
        """官方机器人在 ``group_openid`` 收到 ``member_openid`` 发的 ``text``"""
        if (sent := self._echo_of("official", text, now)) is None:
            return False
        self._learn_group(
            group_openid,
            app_id,
            int(sent.group),
            sent.self_id,
            _weight(sent.text),
            member_openid,
        )
        return True

    def observe_client(
        self,
        client_id: str,
        group_id: int,
        sender_id: str,
        text: str,
        now: float | None = None,
    ) -> bool:
        """QQ 号机器人在 ``group_id`` 收到 ``sender_id`` 发的 ``text``"""
        if (sent := self._echo_of("client", text, now)) is None:
            return False
        weight = _weight(sent.text)
        self._learn_group(sent.group, sent.self_id, group_id, client_id, weight)
        self._learn_official(sender_id, sent.self_id, weight)
        return True

    def _learn_group(
        self,
        group_openid: str,
        app_id: str,
        group_id: int,
        client_id: str,
        weight: int,
        member_openid: str | None = None,
    ) -> None:
        group = self.groups.get(group_openid)
        if group is not None and (
            (group.app_id, group.group_id, group.client_id)
            != (app_id, group_id, client_id)
            or (member_openid and group.member_openid not in (None, member_openid))
        ):
            logger.warning(
                f"群 {group_openid} 的同群关系变了（原先是 {group.group_id}），重新认"
            )
            group = None
        if group is None:
            group = SharedGroup(
                group_openid=group_openid,
                app_id=app_id,
                group_id=group_id,
                client_id=client_id,
            )
            self.groups[group_openid] = group

        before = group.model_copy()
        was_confirmed = group.confirmed
        group.score = min(group.score + weight, CONFIRMED)
        group.member_openid = member_openid or group.member_openid
        if group != before:
            self.save()
        if group.confirmed and not was_confirmed:
            logger.success(
                f"认出同群：群 {group_id} = 官方机器人 {app_id} 的 {group_openid}，"
                f"之后这个群由 QQ 号机器人 {client_id} 处理"
            )

    def _learn_official(self, uin: str, app_id: str, weight: int) -> None:
        account = self.officials.get(uin)
        if account is None or account.app_id != app_id:
            account = self.officials[uin] = OfficialAccount(uin=uin, app_id=app_id)
        was_confirmed = account.confirmed
        score = min(account.score + weight, CONFIRMED)
        if score != account.score:
            account.score = score
            self.save()
        if account.confirmed and not was_confirmed:
            logger.success(f"认出官方机器人 {app_id} 的 QQ 号：{uin}")

    # region 遗忘

    def forget_client_group(self, client_id: str, group_id: int) -> None:
        """QQ 号机器人退群/被踢/群解散"""
        gone = [
            openid
            for openid, group in self.groups.items()
            if group.client_id == client_id and group.group_id == group_id
        ]
        for openid in gone:
            del self.groups[openid]
        if gone:
            logger.info(f"QQ 号机器人 {client_id} 已不在群 {group_id}，忘掉同群关系")
            self.save()

    def forget_official_group(self, group_openid: str) -> None:
        """官方机器人被移出群"""
        if self.groups.pop(group_openid, None) is not None:
            logger.info(f"官方机器人已不在群 {group_openid}，忘掉同群关系")
            self.save()
