from abc import ABC, abstractmethod
from dataclasses import dataclass

from nonebot_plugin_alconna.uniseg import Segment, Text, UniMessage

from src.plugins.bison.plugin_config import plugin_config
from src.plugins.bison.utils import text_to_image


@dataclass(kw_only=True)
class AbstractPost(ABC):
    compress: bool = False
    extra_msg: list[UniMessage] | None = None

    @abstractmethod
    async def generate(self) -> list[Segment]:
        "Generate Segment list from this instance"
        ...

    async def generate_messages(self) -> list[UniMessage]:
        "really call to generate messages"
        segments = await self.generate()
        segments = await self.message_segments_process(segments)
        msgs = await self.message_process(segments)
        return msgs

    async def message_segments_process(self, segments: list[Segment]) -> list[Segment]:
        "generate message segments and process them"

        async def convert(msg: Segment) -> Segment:
            if isinstance(msg, Text):
                return await text_to_image(msg)
            else:
                return msg

        if plugin_config.bison_use_pic:
            return [await convert(msg) for msg in segments]

        return segments

    async def message_process(self, segments: list[Segment]) -> list[UniMessage]:
        "generate messages and process them"
        if self.compress:
            msgs = [UniMessage(segments)]
        else:
            msgs = [UniMessage(segment) for segment in segments]

        if self.extra_msg:
            msgs.extend(self.extra_msg)

        return msgs
