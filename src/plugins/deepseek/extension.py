import inspect

from nonebot.internal.adapter import Bot, Event, Message
from nonebot.typing import T_State
from nonebot_plugin_alconna import Alconna, Arparma, OptionResult, Text
from nonebot_plugin_alconna.extension import Extension
from nonebot_plugin_alconna.uniseg import UniMessage


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
