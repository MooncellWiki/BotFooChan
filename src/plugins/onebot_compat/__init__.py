"""OneBot v11 HTTP API 的兼容层，背后由 Milky 协议端发送。

QQ 号机器人从 NapCat（OneBot v11）换成了 Yogurt（Milky），外部还有一些推送是直接调
OneBot HTTP API 发群消息的（Argo CD 的发版通知、FGONewsMonitor 等）。这里接住其中
发消息的几个接口，翻译成 Milky 再发出去，调用方不用改。

Caddy 把 onebot.bakacraft.net 和本机 5700 端口转到 ``/onebot-compat/<action>``；
鉴权同 OneBot v11：``Authorization: Bearer <token>`` 或 ``?access_token=<token>``。
"""

import hmac
from typing import Any
from urllib.parse import parse_qsl

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import nonebot
from nonebot import logger
from nonebot.adapters.milky import Bot as MilkyBot
from nonebot.adapters.milky.exception import MilkyAdapterException
from nonebot.plugin import PluginMetadata

from .config import Config, plugin_config
from .convert import UnsupportedMessage, parse_onebot_message, to_milky

__plugin_meta__ = PluginMetadata(
    "OneBot v11 HTTP 兼容层",
    "让还在调 OneBot v11 HTTP API 的外部推送经 Milky 协议端发出",
    "POST /onebot-compat/send_group_msg | send_private_msg | send_msg | get_login_info",
    config=Config,
)

app: FastAPI = nonebot.get_app()

# OneBot v11 的 retcode
RETCODE_BAD_PARAMS = 100
RETCODE_FAILED = 103


def _response(
    data: Any = None, retcode: int = 0, message: str = "", status_code: int = 200
) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok" if retcode == 0 else "failed",
            "retcode": retcode,
            "data": data,
            "message": message,
            "wording": message,
        },
        status_code=status_code,
    )


def _check_token(request: Request) -> JSONResponse | None:
    token = plugin_config.onebot_compat_access_token
    if not token:
        return _response(retcode=RETCODE_FAILED, message="接口未启用", status_code=404)

    authorization = request.headers.get("authorization", "")
    given = (
        authorization.removeprefix("Bearer ").strip()
        if authorization.startswith("Bearer ")
        else request.query_params.get("access_token", "")
    )
    if not given:
        return _response(retcode=RETCODE_FAILED, message="缺少 token", status_code=401)
    if not hmac.compare_digest(given, token):
        return _response(retcode=RETCODE_FAILED, message="token 不对", status_code=403)


async def _params(request: Request) -> dict[str, Any]:
    params: dict[str, Any] = {
        k: v for k, v in request.query_params.items() if k != "access_token"
    }
    if request.method == "POST":
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            body = await request.json()
            if not isinstance(body, dict):
                raise UnsupportedMessage("请求体应为 JSON 对象")
            params.update(body)
        elif content_type.startswith("application/x-www-form-urlencoded"):
            # starlette 解析表单要装 python-multipart，urlencoded 用标准库就够了
            params.update(parse_qsl((await request.body()).decode()))
    return params


def _get_bot() -> MilkyBot | None:
    return next(
        (bot for bot in nonebot.get_bots().values() if isinstance(bot, MilkyBot)), None
    )


def _truthy(value: Any) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes"}


async def _send(bot: MilkyBot, params: dict[str, Any], message_type: str) -> int:
    message = to_milky(
        parse_onebot_message(
            params.get("message"), auto_escape=_truthy(params.get("auto_escape"))
        )
    )
    if message_type == "group":
        result = await bot.send_group_message(
            group_id=int(params["group_id"]), message=message
        )
    else:
        result = await bot.send_private_message(
            user_id=int(params["user_id"]), message=message
        )
    return result.message_seq


@app.api_route("/onebot-compat/{action}", methods=["GET", "POST"])
async def onebot_compat(action: str, request: Request) -> JSONResponse:
    if (denied := _check_token(request)) is not None:
        return denied

    action = action.removesuffix("_async")
    if action not in {
        "send_group_msg",
        "send_private_msg",
        "send_msg",
        "get_login_info",
    }:
        return _response(
            retcode=RETCODE_FAILED, message="不支持的接口", status_code=404
        )

    if (bot := _get_bot()) is None:
        return _response(retcode=RETCODE_FAILED, message="Milky 协议端未连接")

    try:
        params = await _params(request)
        match action:
            case "get_login_info":
                info = await bot.get_login_info()
                return _response({"user_id": info.uin, "nickname": info.nickname})
            case "send_group_msg":
                message_type = "group"
            case "send_private_msg":
                message_type = "private"
            case _:
                message_type = params.get("message_type") or (
                    "group" if "group_id" in params else "private"
                )
        message_id = await _send(bot, params, message_type)
    except (UnsupportedMessage, KeyError, ValueError, TypeError) as e:
        logger.warning(f"OneBot 兼容接口 {action} 参数不对：{e!r}")
        return _response(retcode=RETCODE_BAD_PARAMS, message=f"参数不对：{e}")
    except MilkyAdapterException as e:
        logger.opt(exception=e).error(f"OneBot 兼容接口 {action} 发送失败")
        return _response(retcode=RETCODE_FAILED, message=f"发送失败：{e!r}")

    return _response({"message_id": message_id})
