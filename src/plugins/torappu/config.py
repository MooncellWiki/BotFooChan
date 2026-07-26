from nonebot import get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    torappu_api_url: str = "https://torappu.prts.wiki"
    torappu_auth_token: str | None = None


plugin_config = get_plugin_config(Config)
