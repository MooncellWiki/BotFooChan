from nonebot import get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    onebot_compat_access_token: str = ""
    """调用方带的 access token（Bearer 头或 access_token 参数），为空时不开放接口"""


plugin_config = get_plugin_config(Config)
