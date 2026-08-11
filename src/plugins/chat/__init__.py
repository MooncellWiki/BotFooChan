"""通用对话插件：被 @ 或被回复时，带着群聊上下文与群友档案让模型接话。

与 deepseek 插件的分工：那边是 ``/ds`` 命令，一问一答、可指定模型、按需渲染成
图片；这边没有命令，只在别的插件都没接手时兜底，回的是一句像群友的短消息。
"""

from nonebot import logger, on_message, require
from nonebot.adapters import Event
from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot.rule import to_me

require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import UniMsg
from nonebot_plugin_alconna.uniseg import get_message_id

from . import handler as handler
from .config import Config, chat_config

__plugin_meta__ = PluginMetadata(
    name="群聊对话",
    description="被 @ 或被回复时，结合群聊上下文与群友档案接话，并自动积累记忆",
    usage="@ 我或回复我的消息即可；我记住的内容用「我的记忆」查看",
    type="application",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
)

# 记录器：优先级最高且不阻断，群里所有消息都要进缓冲——
# 包括那些触发了别的命令的消息，它们同样是上下文的一部分
message_recorder = on_message(priority=1, block=False)

# 对话：排在最末，别的插件都没接手（没有命令匹配并阻断）才轮到它兜底
chat = on_message(rule=to_me(), priority=99, block=True)


@message_recorder.handle()
async def _(event: Event, msg: UniMsg) -> None:
    try:
        handler.recorder.record_event(event, msg, get_message_id(event))
    except Exception as e:
        # 记录失败绝不能影响别的插件处理这条消息
        logger.opt(exception=e).debug("记录群聊消息失败")


@chat.handle()
async def _(event: Event, msg: UniMsg) -> None:
    await handler.handle(event, msg)


if not chat_config.model:
    logger.warning("未配置 CHAT__MODEL，群聊对话插件不会响应 @")
