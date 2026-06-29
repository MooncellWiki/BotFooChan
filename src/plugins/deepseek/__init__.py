from typing import Any

import httpx
from nonebot import get_plugin_config, logger
from nonebot.adapters import Event
from nonebot.plugin import PluginMetadata
from nonebot_plugin_alconna import Alconna, Args, Match, MultiVar, on_alconna

from .config import Config

config = get_plugin_config(Config)
ds_config = config.deepseek

__plugin_meta__ = PluginMetadata(
    name="DeepSeek 群聊版",
    description="群内共享上下文的 DeepSeek 问答",
    usage="/ds <内容> | /ds reset",
    config=Config,
)

# {session_id: [message, ...]}
_sessions: dict[str, list[dict[str, str]]] = {}


async def chat_with_deepseek(messages: list[dict[str, str]]) -> str:
    if not ds_config.api_key:
        raise RuntimeError("未配置 DeepSeek API Key")

    headers = {
        "Authorization": f"Bearer {ds_config.api_key}",
        "Content-Type": "application/json",
    }
    json_data = {
        "model": ds_config.model,
        "messages": messages,
    }

    async with httpx.AsyncClient(timeout=ds_config.timeout) as client:
        response = await client.post(
            f"{ds_config.base_url}/chat/completions",
            headers=headers,
            json=json_data,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()

    if error := data.get("error"):
        raise RuntimeError(error.get("message", "DeepSeek API 返回错误"))

    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError) as e:
        raise RuntimeError("DeepSeek 返回格式异常") from e

    content = message.get("content", "")
    return content.strip()


def _get_session_id(event: Event) -> str:
    """按群（或频道）隔离会话；私聊按用户隔离。"""
    message_type = getattr(event, "message_type", None)
    if message_type == "group":
        group_id = getattr(event, "group_id", None)
        if group_id is not None:
            return f"group_{group_id}"
    if message_type == "private":
        return f"private_{event.get_user_id()}"
    guild_id = getattr(event, "guild_id", None)
    channel_id = getattr(event, "channel_id", None)
    if guild_id is not None and channel_id is not None:
        return f"guild_{guild_id}_{channel_id}"
    return event.get_session_id()


def _get_user_name(event: Event) -> str:
    user_id = event.get_user_id()
    try:
        sender = getattr(event, "sender", None)
        if sender:
            nickname = getattr(sender, "nickname", None)
            if nickname:
                return str(nickname)
    except Exception:
        pass
    return user_id


def _trim_history(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    limit = ds_config.max_history
    if len(messages) > limit:
        return messages[-limit:]
    return messages


deepseek_cmd = on_alconna(
    Alconna("deepseek", Args["content?", MultiVar("str")]),
    aliases={"ds"},
    use_cmd_start=True,
)


@deepseek_cmd.handle()
async def handle_deepseek(event: Event, content: Match[tuple[str, ...]]) -> None:
    if not content.available:
        await deepseek_cmd.finish(__plugin_meta__.usage)

    text = " ".join(content.result).strip()
    if not text:
        await deepseek_cmd.finish(__plugin_meta__.usage)

    session_id = _get_session_id(event)

    if text.lower() == "reset":
        _sessions.pop(session_id, None)
        await deepseek_cmd.finish("已重置当前会话")

    user_name = _get_user_name(event)
    messages = _sessions.setdefault(session_id, [])
    messages.append({"role": "user", "content": f"[{user_name}] {text}"})
    messages = _trim_history(messages)
    _sessions[session_id] = messages

    try:
        reply = await chat_with_deepseek(messages)
    except httpx.HTTPError as e:
        logger.opt(colors=True, exception=e).error("DeepSeek API request failed")
        await deepseek_cmd.finish(f"请求 DeepSeek 失败：\n{e!r}")
    except RuntimeError as e:
        await deepseek_cmd.finish(str(e))
    except Exception as e:
        logger.opt(colors=True, exception=e).error("Unexpected DeepSeek error")
        await deepseek_cmd.finish(f"DeepSeek 发生未知错误：\n{e!r}")

    messages.append({"role": "assistant", "content": reply})
    messages = _trim_history(messages)
    _sessions[session_id] = messages

    await deepseek_cmd.finish(reply)
