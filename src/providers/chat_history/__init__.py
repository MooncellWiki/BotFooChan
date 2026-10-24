"""会话消息记录 provider。

光看触发命令的那一句话经常不知所云——「这个怎么搞」指的是上面哪条得看上下文。
这里用一个全局的 ``on_message`` 钩子把每个会话最近的消息记在内存里（见
:mod:`.buffer`），供各插件拼上下文：

- 通用对话被 @ 时直接带上最近的若干条
- 需要按需往前翻的用 :class:`.window.HistoryWindow`：预先给几条，
  不够再由模型用工具自己往前翻
"""

from nonebot import logger, on_message, require
from nonebot.adapters import Event

require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import UniMsg
from nonebot_plugin_alconna.uniseg import get_message_id

from .buffer import TZ as TZ
from .buffer import Record as Record
from .buffer import display_name as display_name
from .buffer import recorder as recorder
from .buffer import render_text as render_text
from .buffer import scope_id as scope_id
from .buffer import segment_text as segment_text
from .buffer import sender_name as sender_name
from .config import history_config as history_config
from .window import HistoryWindow as HistoryWindow
from .window import format_record as format_record
from .window import format_records as format_records

# 优先级最高且不阻断，所有消息都要进缓冲——
# 包括那些触发了别的命令的消息，它们同样是上下文的一部分
_message_recorder = on_message(priority=1, block=False)


@_message_recorder.handle()
async def _(event: Event, msg: UniMsg) -> None:
    try:
        recorder.record_event(event, msg, get_message_id(event))
    except Exception as e:
        # 记录失败绝不能影响别的插件处理这条消息
        logger.opt(exception=e).debug("记录会话消息失败")
