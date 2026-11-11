from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict, Field

from src.providers.settings import register


class Config(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    torappu_api_url: str = "https://torappu.prts.wiki"
    """torappu 接口地址"""
    torappu_auth_token: str | None = Field(
        default=None, json_schema_extra={"secret": True}
    )
    """发起重跑用的 token，不配时 /重跑 不可用"""


plugin_config = register(
    "torappu",
    Config,
    title="Torappu",
    description="明日方舟解包数据查询与重跑",
    env=lambda: get_plugin_config(Config),
)
