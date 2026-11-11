"""GitHub OAuth 登录。

借的是 GITHUB_APPS 里那个 GitHub App（也可以单独配一个 OAuth App），回调地址
``<WEBUI__PUBLIC_URL>/admin/api/auth/callback`` 要加进应用设置的 Callback URL 里。
GitHub 插件的 ``/github/auth`` 是给群友绑定账号用的，和这里互不相干。
"""

import hmac
import secrets
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import RedirectResponse
import httpx
from nonebot import logger

from src.plugins.webui.auth import (
    Admin,
    clear_session,
    is_admin,
    is_secure,
    public_base,
    set_session,
    sign,
    unsign,
)
from src.plugins.webui.config import API_PATH, BASE_PATH, oauth_credentials

from .common import Ok

router = APIRouter(prefix="/auth", tags=["auth"])

STATE_COOKIE = "webui_oauth_state"
STATE_TTL = 10 * 60
"""从跳去 GitHub 到回调回来最多等多久（秒）"""

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"
GITHUB_API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _callback_url(request: Request) -> str:
    return f"{public_base(request)}{API_PATH}/auth/callback"


def _safe_next(next_url: str | None) -> str:
    # 登录完只许跳回 WebUI 自己的页面，不然就成了开放重定向
    if next_url and next_url.startswith(f"{BASE_PATH}/"):
        return next_url
    return f"{BASE_PATH}/"


def _login_page(error: str, **params: str) -> RedirectResponse:
    query = urlencode({"error": error, **params})
    return RedirectResponse(
        f"{BASE_PATH}/login?{query}", status_code=status.HTTP_303_SEE_OTHER
    )


async def _revoke_token(
    client: httpx.AsyncClient, credentials: tuple[str, str], token: str
) -> None:
    # 用户名到手 token 就没用了，顺手吊销：同一个应用发给同一个用户的 token 有数量
    # 上限，超了会把最早的挤掉，而 GitHub 插件存着的 /auth 授权可能也是这个应用发的
    client_id, client_secret = credentials
    try:
        response = await client.request(
            "DELETE",
            f"{GITHUB_API_URL}/applications/{client_id}/token",
            auth=(client_id, client_secret),
            json={"access_token": token},
            headers=GITHUB_API_HEADERS,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning(f"吊销 WebUI 登录用的 GitHub token 失败：{e!r}")


async def _fetch_github_user(
    credentials: tuple[str, str], code: str, redirect_uri: str
) -> Admin:
    client_id, client_secret = credentials
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        if not (token := payload.get("access_token")):
            raise RuntimeError(
                f"GitHub 没给 token：{payload.get('error_description') or payload}"
            )
        try:
            response = await client.get(
                f"{GITHUB_API_URL}/user",
                headers={**GITHUB_API_HEADERS, "Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            user = response.json()
        finally:
            await _revoke_token(client, credentials, token)
    return Admin(
        login=user["login"],
        name=user.get("name") or "",
        avatar_url=user.get("avatar_url") or "",
    )


@router.get("/login", include_in_schema=False)
async def login(
    request: Request, next_url: Annotated[str | None, Query(alias="next")] = None
) -> RedirectResponse:
    """跳去 GitHub 授权"""
    credentials = oauth_credentials()
    if credentials is None:
        return _login_page("unavailable")
    state = secrets.token_urlsafe(24)
    query = urlencode(
        {
            "client_id": credentials[0],
            "redirect_uri": _callback_url(request),
            "state": state,
            "allow_signup": "false",
        }
    )
    response = RedirectResponse(
        f"{GITHUB_AUTHORIZE_URL}?{query}", status_code=status.HTTP_303_SEE_OTHER
    )
    response.set_cookie(
        STATE_COOKIE,
        sign("oauth-state", {"state": state, "next": _safe_next(next_url)}, STATE_TTL),
        max_age=STATE_TTL,
        path=f"{API_PATH}/auth",
        httponly=True,
        secure=is_secure(request),
        samesite="lax",
    )
    return response


async def _finish_login(
    request: Request, code: str | None, state: str | None
) -> RedirectResponse:
    if not code:
        return _login_page("denied")
    saved = unsign("oauth-state", request.cookies.get(STATE_COOKIE))
    if (
        saved is None
        or not state
        or not hmac.compare_digest(str(saved.get("state")).encode(), state.encode())
    ):
        return _login_page("expired")
    if (credentials := oauth_credentials()) is None:
        return _login_page("unavailable")

    try:
        admin = await _fetch_github_user(credentials, code, _callback_url(request))
    except Exception as e:
        logger.opt(exception=e).error("WebUI 的 GitHub 登录失败")
        return _login_page("github")

    if not is_admin(admin.login):
        logger.warning(f"GitHub 用户 {admin.login} 想登录 WebUI，不在 WEBUI__ADMINS 里")
        return _login_page("forbidden", login=admin.login)

    logger.info(f"GitHub 用户 {admin.login} 登录了 WebUI")
    response = RedirectResponse(
        _safe_next(saved.get("next")), status_code=status.HTTP_303_SEE_OTHER
    )
    set_session(response, request, admin)
    return response


@router.get("/callback", include_in_schema=False)
async def callback(
    request: Request, code: str | None = None, state: str | None = None
) -> RedirectResponse:
    """GitHub 授权完跳回这里"""
    response = await _finish_login(request, code, state)
    response.delete_cookie(
        STATE_COOKIE,
        path=f"{API_PATH}/auth",
        httponly=True,
        secure=is_secure(request),
        samesite="lax",
    )
    return response


@router.post("/logout")
async def logout(request: Request, response: Response) -> Ok:
    """退出登录"""
    clear_session(response, request)
    return Ok()
