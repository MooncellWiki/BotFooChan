import inspect

from arclet.alconna import output_manager
from nonebot.internal.adapter import Bot, Event, Message
from nonebot.typing import T_State
from nonebot_plugin_alconna import Alconna, Arparma, OptionResult, Text
from nonebot_plugin_alconna.extension import Extension
from nonebot_plugin_alconna.uniseg import UniMessage, reply_fetch


class ReplyMergeExtension(Extension):
    """将被回复消息的内容并入参数，但仅在当前消息自身已经触发命令时生效。

    alconna 内置的 ReplyMergeExtension 无条件合并，会导致「用户 A 发送
    `ds xxx`，用户 B 回复这条消息」时，A 的命令文本被并入 B 的消息而误触发。
    """

    def __init__(self, sep: str = " ") -> None:
        self.sep = sep

    @property
    def priority(self) -> int:
        return 14

    @property
    def id(self) -> str:
        return "ReplyMergeExtension"

    async def receive_wrapper(
        self, bot: Bot, event: Event, command: Alconna, receive: UniMessage
    ) -> UniMessage:
        reply = await reply_fetch(event, bot)
        if not reply or not reply.msg:
            return receive

        # 命令必须由当前消息发起，被回复的消息只能作为附加参数
        try:
            with output_manager.capture(command.name):
                output_manager.set_action(lambda x: x, command.name)
                if not command.parse(receive.include(Text)).head_matched:
                    return receive
        except Exception:
            return receive

        reply_msg = reply.msg
        if isinstance(reply_msg, str):
            reply_msg = event.get_message().__class__(reply_msg)
        return receive + self.sep + UniMessage.of(reply_msg, bot=bot)


class CleanDocExtension(Extension):
    @property
    def priority(self) -> int:
        return 15

    @property
    def id(self) -> str:
        return "CleanDoc"

    async def send_wrapper(
        self, bot: Bot, event: Event, send: str | Message | UniMessage
    ):
        plain_text = (
            send if isinstance(send, Message | UniMessage) else inspect.cleandoc(send)
        )
        return plain_text


class ParseExtension(Extension):
    @property
    def priority(self) -> int:
        return 20

    @property
    def id(self) -> str:
        return "ParseExtension"

    async def parse_wrapper(
        self, bot: Bot, state: T_State, event: Event, res: Arparma
    ) -> None:
        if res.subcommands.get("model") and not res.subcommands["model"].options:
            res.subcommands["model"].options.setdefault("list", OptionResult())

    async def receive_wrapper(
        self, bot: Bot, event: Event, command: Alconna, receive: UniMessage
    ) -> UniMessage:
        return receive.include(Text)
