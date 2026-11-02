"""OneBot v11 HTTP API 的兼容层，背后由 QQ 官方机器人发送。

外部还有一些推送是直接调 OneBot HTTP API 发群消息的（Argo CD 的发版通知、
FGONewsMonitor 等）。这里接住其中发消息的几个接口，翻译成官方机器人的消息再发出去，
调用方不用改。

官方机器人只认 group_openid，调用方给的群号要先在群里用 ``/llm bind`` 绑定
（见 :mod:`src.plugins.chat.binding`）；没绑定的群也可以直接把 group_openid 当
group_id 传。私聊同理，只能直接传用户的 openid，QQ 号换算不过去。
官方机器人发的是主动消息，受官方的主动推送额度和频率限制，超额时接口直接报错。

Caddy 把 onebot.bakacraft.net 和本机 5700 端口转到 ``/onebot-compat/<action>``；
鉴权同 OneBot v11：``Authorization: Bearer <token>`` 或 ``?access_token=<token>``。
"""

import hmac
from typing import Any
from urllib.parse import parse_qsl

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import nonebot
from nonebot import logger, require
from nonebot.adapters.qq import Bot as QQBot
from nonebot.adapters.qq.exception import QQAdapterException
from nonebot.plugin import PluginMetadata

require("chat")
from src.plugins.chat.binding import group_bindings
from src.plugins.chat.markdown import get_qq_bots, resolve_bot

from .config import Config, plugin_config
from .convert import UnsupportedMessage, parse_onebot_message, to_qq

__plugin_meta__ = PluginMetadata(
    "OneBot v11 HTTP 兼容层",
    "让还在调 OneBot v11 HTTP API 的外部推送经 QQ 官方机器人发出",
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


class UnknownTarget(ValueError):
    pass


class BotOffline(Exception):
    pass


def _only_bot() -> QQBot | None:
    """不知道 openid 归哪个机器人时，只有一个官方机器人在线才敢用"""
    bots = get_qq_bots()
    return bots[0] if len(bots) == 1 else None


def _group_target(group_id: str) -> tuple[QQBot, str]:
    if (binding := group_bindings.get(group_id)) is not None:
        bot, openid = resolve_bot(binding), binding.group_openid
    elif not group_id.isdigit():
        bot, openid = _only_bot(), group_id
    else:
        raise UnknownTarget(
            f"群 {group_id} 没有绑定官方机器人的 group_openid，先在群里 /llm bind"
        )
    if bot is None:
        raise BotOffline(f"群 {group_id} 对应的官方机器人不在线")
    return bot, openid


def _private_target(user_id: str) -> tuple[QQBot, str]:
    if user_id.isdigit():
        raise UnknownTarget("官方机器人只能按 openid 私聊，QQ 号换算不过去")
    if (bot := _only_bot()) is None:
        raise BotOffline("没有唯一在线的官方机器人可以私聊")
    return bot, user_id


def _truthy(value: Any) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes"}


async def _send(params: dict[str, Any], message_type: str) -> str | None:
    """拆成几条发时返回第一条的消息 id"""
    messages = to_qq(
        parse_onebot_message(
            params.get("message"), auto_escape=_truthy(params.get("auto_escape"))
        )
    )
    if message_type == "group":
        bot, openid = _group_target(str(params["group_id"]))
        send = bot.send_to_group
    else:
        bot, openid = _private_target(str(params["user_id"]))
        send = bot.send_to_c2c

    first_id = None
    for message in messages:
        result = await send(openid, message=message)
        # 返回值类型标注里带着上传文件的结果，实际总是发消息接口的返回
        first_id = first_id or getattr(result, "id", None)
    return first_id


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

    if not (bots := get_qq_bots()):
        return _response(retcode=RETCODE_FAILED, message="官方机器人未连接")

    try:
        params = await _params(request)
        match action:
            case "get_login_info":
                bot = bots[0]
                return _response(
                    {"user_id": bot.self_id, "nickname": bot.self_info.username}
                )
            case "send_group_msg":
                message_type = "group"
            case "send_private_msg":
                message_type = "private"
            case _:
                message_type = params.get("message_type") or (
                    "group" if "group_id" in params else "private"
                )
        message_id = await _send(params, message_type)
    except BotOffline as e:
        return _response(retcode=RETCODE_FAILED, message=str(e))
    except (UnsupportedMessage, UnknownTarget, KeyError, ValueError, TypeError) as e:
        logger.warning(f"OneBot 兼容接口 {action} 参数不对：{e!r}")
        return _response(retcode=RETCODE_BAD_PARAMS, message=f"参数不对：{e}")
    except QQAdapterException as e:
        logger.opt(exception=e).error(f"OneBot 兼容接口 {action} 发送失败")
        return _response(retcode=RETCODE_FAILED, message=f"发送失败：{e!r}")

    return _response({"message_id": message_id})
