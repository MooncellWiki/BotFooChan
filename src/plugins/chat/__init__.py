"""通用对话插件：被 @ 或被回复时，带着群聊上下文与群友档案让模型接话。

闲聊回一两句像群友的话；认真提问给完整回答，长回答连同思维链、联网来源排版成
图片（绑定了官方机器人的群走原生 markdown）。回复机器人的某条回答就接着那段对话聊，
提问和被引用消息里的图片都会交给模型看。

原先的 /ds 命令（迁移自 nonebot-plugin-deepseek，原作者 Komorebi，MIT License）
已并入这里；它的管理功能挪到了 /llm，见 :mod:`.admin`。
"""

from nonebot import logger, on_message, require
from nonebot.adapters import Bot, Event
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_htmlrender")
from nonebot_plugin_alconna import UniMsg

from . import admin as admin
from . import handler as handler
from .config import Config, current_model
from .rule import should_reply

__plugin_meta__ = PluginMetadata(
    name="群聊对话",
    description="被 @ 或被回复时，结合群聊上下文与群友档案接话，并自动积累记忆",
    usage=(
        "@ 我或回复我的消息即可，可以带图；回复我的回答就能接着聊\n"
        "我记住的内容用「我的记忆」查看；管理指令见 /llm"
    ),
    type="application",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
)

# 聊天记录由 src.providers.chat_history 统一记录，这里只管接话。
# 排在最末，别的插件都没接手（没有命令匹配并阻断）才轮到它兜底。
# 触发条件不用 to_me()，见 rule.py：那个太宽，两个机器人能靠它自己聊起来
chat = on_message(rule=should_reply, priority=99, block=True)


@chat.handle()
async def _(bot: Bot, event: Event, msg: UniMsg) -> None:
    await handler.handle(bot, event, msg)


if not current_model():
    logger.warning("未配置 CHAT__MODEL，群聊对话插件不会响应 @")
