from enum import Enum

from pydantic.fields import Field
from nonebot.config import BaseConfig
from pydantic import AnyHttpUrl, PositiveInt


class LinkType(str, Enum):
    hard = "hard"
    soft = "soft"


class Config(BaseConfig):
    filehost_fallback_host: AnyHttpUrl | None = Field(...)
    filehost_link_file: PositiveInt | bool = True
    filehost_link_type: LinkType = LinkType.hard

    class Config:
        extra = "ignore"
