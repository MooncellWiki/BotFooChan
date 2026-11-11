"""登录态与请求校验。

GitHub OAuth 换出用户名、比对白名单之后（见 :mod:`.api.auth`），发一个 HMAC 签名的
cookie，里面只有用户名、昵称、头像和过期时间，服务端不存会话。每个请求都重新比对
白名单，所以把人从 WEBUI__ADMINS 里删掉立刻失效。

写接口另外要求带 ``X-WebUI`` 头：没放行 CORS，跨站页面带不上自定义头，以此挡 CSRF。
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, Response, status
from nonebot import logger
from pydantic import BaseModel, ValidationError

from .config import BASE_PATH, dev_admin, is_dev, webui_config

SESSION_COOKIE = "webui_session"
CSRF_HEADER = "X-WebUI"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _load_secret() -> bytes | None:
    if webui_config.secret_key:
        return webui_config.secret_key.encode()
    if is_dev():
        logger.warning("没配 WEBUI__SECRET_KEY，临时生成了一个，重启后要重新登录")
        return secrets.token_bytes(32)
    return None


SECRET = _load_secret()
"""签名用的密钥；为 None 时 WebUI 不启用"""


class Admin(BaseModel):
    """登录的管理员（GitHub 账号）"""

    login: str
    name: str = ""
    avatar_url: str = ""


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signature(purpose: str, body: str) -> str:
    if SECRET is None:
        raise RuntimeError("WebUI 没有签名密钥")
    # 按用途派生子密钥：OAuth state 的签名不能拿来冒充登录 cookie
    key = hmac.new(SECRET, f"webui:{purpose}".encode(), hashlib.sha256).digest()
    return _b64encode(hmac.new(key, body.encode(), hashlib.sha256).digest())


def sign(purpose: str, data: dict[str, Any], ttl: int) -> str:
    """把 data 连同过期时间签成一个 token"""
    payload = {**data, "exp": int(time.time()) + ttl}
    body = _b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    )
    return f"{body}.{_signature(purpose, body)}"


def unsign(purpose: str, token: str | None) -> dict[str, Any] | None:
    """校验 token，返回签进去的 data；签名不对或过期时为 None"""
    if not token or SECRET is None:
        return None
    body, _, signature = token.partition(".")
    if not hmac.compare_digest(signature.encode(), _signature(purpose, body).encode()):
        return None
    try:
        data = json.loads(_b64decode(body))
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    expires = data.get("exp")
    if not isinstance(expires, int) or expires < time.time():
        return None
    return data


def is_admin(login: str) -> bool:
    login = login.lower()
    return login in webui_config.admins or login == dev_admin()


def public_base(request: Request) -> str:
    """对外访问的 scheme://host[:port]"""
    # 挂载的子应用里 request.base_url 带着挂载路径，所以自己拼
    return webui_config.public_url or f"{request.url.scheme}://{request.url.netloc}"


def is_secure(request: Request) -> bool:
    return public_base(request).startswith("https://")


def set_session(response: Response, request: Request, admin: Admin) -> None:
    ttl = webui_config.session_days * 24 * 60 * 60
    response.set_cookie(
        SESSION_COOKIE,
        sign("session", admin.model_dump(), ttl),
        max_age=ttl,
        path=BASE_PATH,
        httponly=True,
        secure=is_secure(request),
        samesite="lax",
    )


def clear_session(response: Response, request: Request) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path=BASE_PATH,
        httponly=True,
        secure=is_secure(request),
        samesite="lax",
    )


def _session_admin(request: Request) -> Admin | None:
    data = unsign("session", request.cookies.get(SESSION_COOKIE))
    if data is None:
        return None
    try:
        admin = Admin.model_validate(data)
    except ValidationError:
        return None
    return admin if is_admin(admin.login) else None


async def require_admin(request: Request) -> Admin:
    """当前登录的管理员；没登录时 401"""
    if admin := _session_admin(request):
        return admin
    if login := dev_admin():
        return Admin(login=login, name=f"{login}（开发模式）")
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "没有登录或登录已过期")


CurrentAdmin = Annotated[Admin, Depends(require_admin)]


async def check_csrf(request: Request) -> None:
    if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"缺少 {CSRF_HEADER} 请求头")
