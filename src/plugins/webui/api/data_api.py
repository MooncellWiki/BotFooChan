"""业务数据：bison 订阅、GitHub 绑定与订阅、群号绑定、FGO 维护推送、群友记忆。

都走各插件自己的读写函数（会触发调度器刷新、绑定回调之类的副作用），不直接改表。
对应插件没加载时接口返回 503。
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Query
import nonebot
from nonebot_plugin_orm import get_session
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from src.plugins.webui.auth import CurrentAdmin
from src.providers.settings import audit

from .common import (
    Ok,
    Page,
    actor,
    aware,
    bad_request,
    conflict,
    not_found,
    unavailable,
)

router = APIRouter(tags=["data"])


def _require(plugin: str, what: str) -> None:
    if nonebot.get_plugin(plugin) is None:
        raise unavailable(f"{what}插件没有加载")


def target_label(data: dict[str, Any]) -> str:
    """把各插件存的「会话」字典写成一行字。

    bison 存的是 alconna 的 Target（scope、id……），
    GitHub 存的是 TargetInfo（type、各种 id）
    """
    kind = data.get("scope") or data.get("type") or "?"
    if data.get("private") is True:
        kind = f"{kind} 私聊"
    ids = [
        str(v)
        for k, v in data.items()
        if k
        not in {"scope", "type", "private", "channel", "extra", "self_id", "parent_id"}
        and v not in (None, "", False, {}, [])
    ]
    return f"{kind} {' / '.join(ids)}".strip()


# ---------- bison ----------


class BisonPlatform(BaseModel):
    name: str
    display_name: str
    has_target: bool
    enable_tag: bool
    categories: dict[int, str]


class BisonSubscription(BaseModel):
    id: int
    user_target: dict[str, Any]
    user_label: str
    platform: str
    target: str
    target_name: str
    categories: list[int]
    tags: list[str]


class BisonCookie(BaseModel):
    id: int
    site_name: str
    cookie_name: str
    status: str
    last_usage: datetime | None
    is_universal: bool
    is_anonymous: bool
    targets: list[str]
    """关联的订阅对象（平台 / 名称）"""


class BisonOverview(BaseModel):
    platforms: list[BisonPlatform]
    subscriptions: list[BisonSubscription]
    cookies: list[BisonCookie]


async def _bison_overview() -> BisonOverview:
    from sqlalchemy.orm import selectinload

    from src.plugins.bison.config import config
    from src.plugins.bison.config.db_model import Cookie, CookieTarget, Target
    from src.plugins.bison.platform import platform_manager

    subs = await config.list_subs_with_all_info()
    async with get_session() as session:
        cookies = (
            await session.scalars(
                select(Cookie).options(
                    selectinload(Cookie.targets).selectinload(CookieTarget.target)
                )
            )
        ).all()
    return BisonOverview(
        platforms=[
            BisonPlatform(
                name=name,
                display_name=p.name,
                has_target=p.has_target,
                enable_tag=p.enable_tag,
                categories=dict(getattr(p, "categories", {}) or {}),
            )
            for name, p in sorted(platform_manager.items())
        ],
        subscriptions=[
            BisonSubscription(
                id=s.id,
                user_target=s.user.user_target,
                user_label=target_label(s.user.user_target),
                platform=s.target.platform_name,
                target=s.target.target,
                target_name=s.target.target_name,
                categories=list(s.categories or []),
                tags=list(s.tags or []),
            )
            for s in sorted(subs, key=lambda s: (str(s.user.user_target), s.id))
        ],
        cookies=[
            BisonCookie(
                id=c.id,
                site_name=c.site_name,
                cookie_name=c.cookie_name,
                status=c.status,
                last_usage=aware(c.last_usage) if c.last_usage else None,
                is_universal=c.is_universal,
                is_anonymous=c.is_anonymous,
                targets=[
                    f"{ct.target.platform_name} / {ct.target.target_name}"
                    for ct in c.targets
                    if isinstance(ct.target, Target)
                ],
            )
            for c in cookies
        ],
    )


@router.get("/bison")
async def get_bison() -> BisonOverview:
    """订阅、平台和 Cookie（不含 Cookie 内容）"""
    _require("bison", "bison ")
    return await _bison_overview()


class BisonSubscriptionIn(BaseModel):
    user_target: dict[str, Any]
    """推送到哪个会话：从已有订阅里选（bison 存的 user_target）"""
    platform: str
    target: str = ""
    categories: list[int] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


@router.post("/bison/subscriptions")
async def add_bison_subscription(
    body: BisonSubscriptionIn, admin: CurrentAdmin
) -> BisonOverview:
    """给一个已有的会话添加订阅"""
    _require("bison", "bison ")
    from src.plugins.bison.apis import check_sub_target
    from src.plugins.bison.config import config
    from src.plugins.bison.config.db_config import SubscribeDupException
    from src.plugins.bison.config.utils import load_send_target
    from src.plugins.bison.platform import platform_manager
    from src.plugins.bison.types import Target as T_Target

    platform = platform_manager.get(body.platform)
    if platform is None:
        raise not_found(f"平台 {body.platform} ")
    if platform.has_target:
        if not body.target:
            raise bad_request(f"{platform.name} 要填订阅对象")
        try:
            name = await check_sub_target(body.platform, T_Target(body.target))
        except Exception as e:
            raise bad_request(f"查不到这个订阅对象：{e!r}") from e
        if not name:
            raise bad_request("查不到这个订阅对象，检查一下 id")
    else:
        name = platform.name
    try:
        await config.add_subscribe(
            load_send_target(body.user_target),
            T_Target(body.target),
            name,
            body.platform,
            body.categories,
            body.tags,
        )
    except SubscribeDupException as e:
        raise conflict("这个会话已经订阅过它了") from e
    await audit(
        actor(admin),
        "bison",
        "subscribe",
        {
            "user": target_label(body.user_target),
            "platform": body.platform,
            "target": body.target,
            "name": name,
        },
    )
    return await _bison_overview()


async def _find_subscription(subscription_id: int) -> Any:
    from sqlalchemy.orm import selectinload

    from src.plugins.bison.config.db_model import Subscribe

    async with get_session() as session:
        sub = await session.scalar(
            select(Subscribe)
            .where(Subscribe.id == subscription_id)
            .options(selectinload(Subscribe.target), selectinload(Subscribe.user))
        )
    if sub is None:
        raise not_found(f"订阅 {subscription_id} ")
    return sub


class BisonSubscriptionPatch(BaseModel):
    categories: list[int]
    tags: list[str]


@router.put("/bison/subscriptions/{subscription_id}")
async def update_bison_subscription(
    subscription_id: int, body: BisonSubscriptionPatch, admin: CurrentAdmin
) -> BisonOverview:
    """改订阅的分类和标签"""
    _require("bison", "bison ")
    from src.plugins.bison.config import config
    from src.plugins.bison.config.utils import load_send_target

    sub = await _find_subscription(subscription_id)
    await config.update_subscribe(
        load_send_target(sub.user.user_target),
        sub.target.target,
        sub.target.target_name,
        sub.target.platform_name,
        body.categories,
        body.tags,
    )
    await audit(
        actor(admin),
        "bison",
        "update",
        {"id": subscription_id, "categories": body.categories, "tags": body.tags},
    )
    return await _bison_overview()


@router.delete("/bison/subscriptions/{subscription_id}")
async def delete_bison_subscription(
    subscription_id: int, admin: CurrentAdmin
) -> BisonOverview:
    """取消订阅"""
    _require("bison", "bison ")
    from src.plugins.bison.config import config
    from src.plugins.bison.config.utils import load_send_target

    sub = await _find_subscription(subscription_id)
    await config.del_subscribe(
        load_send_target(sub.user.user_target),
        sub.target.target,
        sub.target.platform_name,
    )
    await audit(
        actor(admin),
        "bison",
        "unsubscribe",
        {
            "user": target_label(sub.user.user_target),
            "platform": sub.target.platform_name,
            "target": sub.target.target,
            "name": sub.target.target_name,
        },
    )
    return await _bison_overview()


@router.delete("/bison/cookies/{cookie_id}")
async def delete_bison_cookie(cookie_id: int, admin: CurrentAdmin) -> BisonOverview:
    """删除 Cookie（还关联着订阅对象时不让删）"""
    _require("bison", "bison ")
    from src.plugins.bison.config import NoSuchTargetException, config

    try:
        await config.delete_cookie_by_id(cookie_id)
    except NoSuchTargetException as e:
        raise not_found(f"Cookie {cookie_id} ") from e
    except Exception as e:
        raise conflict("这个 Cookie 还关联着订阅对象，先取消关联") from e
    await audit(actor(admin), "bison", "delete_cookie", {"id": cookie_id})
    return await _bison_overview()


# ---------- GitHub ----------


class GitHubGroup(BaseModel):
    id: int
    label: str
    group: dict[str, Any]
    bind_repo: str | None


class GitHubSubscription(BaseModel):
    id: int
    label: str
    subscriber: dict[str, Any]
    repo: str
    event: str
    action: list[str] | None


class GitHubUser(BaseModel):
    id: int
    label: str
    user: dict[str, Any]
    authorized: bool


class GitHubOverview(BaseModel):
    groups: list[GitHubGroup]
    subscriptions: list[GitHubSubscription]
    users: list[GitHubUser]


async def _github_overview() -> GitHubOverview:
    from src.plugins.github.models import Group, Subscription, User

    async with get_session() as session:
        groups = (await session.scalars(select(Group).order_by(Group.id))).all()
        subs = (
            await session.scalars(select(Subscription).order_by(Subscription.id))
        ).all()
        users = (await session.scalars(select(User).order_by(User.id))).all()
    return GitHubOverview(
        groups=[
            GitHubGroup(
                id=g.id,
                label=target_label(g.group),
                group=g.group,
                bind_repo=g.bind_repo,
            )
            for g in groups
        ],
        subscriptions=[
            GitHubSubscription(
                id=s.id,
                label=target_label(s.subscriber),
                subscriber=s.subscriber,
                repo=f"{s.owner}/{s.repo}",
                event=s.event,
                action=s.action,
            )
            for s in subs
        ],
        users=[
            GitHubUser(
                id=u.id,
                label=target_label(u.user),
                user=u.user,
                authorized=bool(u.access_token),
            )
            for u in users
        ],
    )


@router.get("/github")
async def get_github() -> GitHubOverview:
    """群绑定的仓库、仓库订阅、已授权的用户（不含 token）"""
    _require("github", "GitHub ")
    return await _github_overview()


@router.delete("/github/groups/{group_id}")
async def unbind_github_group(group_id: int, admin: CurrentAdmin) -> GitHubOverview:
    """解除群绑定的仓库"""
    _require("github", "GitHub ")
    from src.plugins.github.models import Group

    async with get_session() as session:
        group = await session.get(Group, group_id)
    if group is None:
        raise not_found(f"群绑定 {group_id} ")
    repo = group.bind_repo
    await group.unbind()
    await audit(
        actor(admin),
        "github",
        "unbind",
        {"group": target_label(group.group), "repo": repo},
    )
    return await _github_overview()


@router.delete("/github/subscriptions/{subscription_id}")
async def delete_github_subscription(
    subscription_id: int, admin: CurrentAdmin
) -> GitHubOverview:
    """删除仓库订阅"""
    _require("github", "GitHub ")
    from src.plugins.github.models import Subscription

    async with get_session() as session:
        sub = await session.get(Subscription, subscription_id)
        if sub is None:
            raise not_found(f"订阅 {subscription_id} ")
        detail = {
            "subscriber": target_label(sub.subscriber),
            "repo": f"{sub.owner}/{sub.repo}",
            "event": sub.event,
        }
        await session.delete(sub)
        await session.commit()
    await audit(actor(admin), "github", "unsubscribe", detail)
    return await _github_overview()


@router.delete("/github/users/{user_id}")
async def unauth_github_user(user_id: int, admin: CurrentAdmin) -> GitHubOverview:
    """撤销用户的 GitHub 授权（删掉存着的 token）"""
    _require("github", "GitHub ")
    from src.plugins.github.models import User

    async with get_session() as session:
        user = await session.get(User, user_id)
    if user is None:
        raise not_found(f"用户 {user_id} ")
    await user.unauth()
    await audit(actor(admin), "github", "unauth", {"user": target_label(user.user)})
    return await _github_overview()


# ---------- 群号绑定 ----------


class GroupBindingOut(BaseModel):
    group_id: str
    group_openid: str
    bot_id: str | None
    online: bool
    """绑定的官方机器人现在在不在线"""
    fgo_push: bool
    """在不在 FGO 维护推送列表里"""


def _fgo_groups() -> list[int]:
    if nonebot.get_plugin("fgo_server_status") is None:
        return []
    from src.plugins.fgo_server_status.storage import load_recv_groups

    return load_recv_groups()


def _bindings() -> list[GroupBindingOut]:
    from src.providers.group_binding import group_bindings, resolve_bot

    fgo = {str(g) for g in _fgo_groups()}
    return [
        GroupBindingOut(
            group_id=group_id,
            group_openid=b.group_openid,
            bot_id=b.bot_id,
            online=resolve_bot(b) is not None,
            fgo_push=group_id in fgo,
        )
        for group_id, b in sorted(group_bindings.bindings.items())
    ]


@router.get("/bindings")
async def list_bindings() -> list[GroupBindingOut]:
    """群号和 QQ 官方机器人 group_openid 的绑定。

    新增要在群里 @ 官方机器人发 /官q 绑定
    """
    return _bindings()


@router.delete("/bindings/{group_id}")
async def delete_binding(group_id: str, admin: CurrentAdmin) -> list[GroupBindingOut]:
    """删除群号绑定"""
    from src.providers.group_binding import group_bindings

    binding = group_bindings.get(group_id)
    if binding is None or not group_bindings.remove(group_id):
        raise not_found(f"群号 {group_id} 的绑定")
    await audit(
        actor(admin),
        "group_binding",
        "remove",
        {"group_id": group_id, "group_openid": binding.group_openid},
    )
    return _bindings()


# ---------- FGO 维护推送 ----------


class FgoPushGroup(BaseModel):
    group_id: int
    bound: bool
    """群号绑定了官方机器人（没绑定的推不出去）"""


def _fgo_list() -> list[FgoPushGroup]:
    from src.providers.group_binding import group_bindings

    return [
        FgoPushGroup(group_id=g, bound=group_bindings.get(str(g)) is not None)
        for g in _fgo_groups()
    ]


@router.get("/fgo/groups")
async def list_fgo_groups() -> list[FgoPushGroup]:
    """接收 FGO 维护推送的群"""
    _require("fgo_server_status", "FGO 服务器状态")
    return _fgo_list()


@router.post("/fgo/groups")
async def add_fgo_group(
    group_id: Annotated[int, Body(embed=True)], admin: CurrentAdmin
) -> list[FgoPushGroup]:
    """开启某个群的维护推送"""
    _require("fgo_server_status", "FGO 服务器状态")
    from src.plugins.fgo_server_status.storage import load_recv_groups, save_recv_groups

    groups = load_recv_groups()
    if group_id in groups:
        raise conflict(f"群 {group_id} 已在推送列表里")
    save_recv_groups([*groups, group_id])
    await audit(actor(admin), "fgo_push", "add", {"group_id": group_id})
    return _fgo_list()


@router.delete("/fgo/groups/{group_id}")
async def remove_fgo_group(group_id: int, admin: CurrentAdmin) -> list[FgoPushGroup]:
    """关闭某个群的维护推送"""
    _require("fgo_server_status", "FGO 服务器状态")
    from src.plugins.fgo_server_status.storage import load_recv_groups, save_recv_groups

    groups = load_recv_groups()
    if group_id not in groups:
        raise not_found(f"推送列表里的群 {group_id} ")
    save_recv_groups([g for g in groups if g != group_id])
    await audit(actor(admin), "fgo_push", "remove", {"group_id": group_id})
    return _fgo_list()


# ---------- 群友记忆 ----------


class MemorySummary(BaseModel):
    user_id: str
    updated_at: datetime
    length: int
    preview: str


class MemoryDetail(BaseModel):
    user_id: str
    updated_at: datetime | None
    content: str


@router.get("/memories")
async def list_memories(
    q: Annotated[str | None, Query(description="用户 id 或档案内容里的字")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[MemorySummary]:
    """有档案的群友，最近更新的在前"""
    from src.providers.user_memory import UserMemory

    conditions = [UserMemory.content != ""]
    if q:
        conditions.append(
            UserMemory.user_id.contains(q) | UserMemory.content.contains(q)
        )
    async with get_session() as session:
        total = await session.scalar(
            select(func.count()).select_from(UserMemory).where(*conditions)
        )
        rows = (
            await session.scalars(
                select(UserMemory)
                .where(*conditions)
                .order_by(UserMemory.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    return Page[MemorySummary](
        items=[
            MemorySummary(
                user_id=r.user_id,
                updated_at=aware(r.updated_at),
                length=len(r.content),
                preview=r.content[:120],
            )
            for r in rows
        ],
        total=total or 0,
    )


async def _memory(user_id: str) -> MemoryDetail:
    from src.providers.user_memory import UserMemory

    async with get_session() as session:
        row = await session.get(UserMemory, user_id)
    return MemoryDetail(
        user_id=user_id,
        updated_at=aware(row.updated_at) if row else None,
        content=row.content if row else "",
    )


@router.get("/memories/{user_id}")
async def get_memory_detail(user_id: str) -> MemoryDetail:
    """一位群友的档案全文"""
    return await _memory(user_id)


@router.put("/memories/{user_id}")
async def put_memory(
    user_id: str,
    content: Annotated[str, Body(embed=True, max_length=20000)],
    admin: CurrentAdmin,
) -> MemoryDetail:
    """整份改写档案（超长时照常会被压缩）"""
    from src.providers.user_memory import set_memory

    await set_memory(user_id, content)
    await audit(actor(admin), "user_memory", "update", {"user_id": user_id})
    return await _memory(user_id)


@router.delete("/memories/{user_id}")
async def delete_memory(user_id: str, admin: CurrentAdmin) -> Ok:
    """清空档案"""
    from src.providers.user_memory import clear_memory

    if not await clear_memory(user_id):
        raise not_found(f"{user_id} 的档案")
    await audit(actor(admin), "user_memory", "clear", {"user_id": user_id})
    return Ok()
