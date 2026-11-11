from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict, Field

from src.providers.settings import register


class Config(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    onebot_compat_access_token: str = Field(
        default="", json_schema_extra={"secret": True}
    )
    """调用方带的 access token（Bearer 头或 access_token 参数），为空时不开放接口"""


plugin_config = register(
    "onebot_compat",
    Config,
    title="OneBot v11 兼容层",
    description="让外部推送经 QQ 官方机器人发出",
    env=lambda: get_plugin_config(Config),
)
