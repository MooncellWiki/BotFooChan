from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict

from src.providers.settings import register


class Config(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    fgo_data_url_cn: str = (
        "https://line1-s1-bili-fate.bilibiligame.net"
        "/rongame_beta/rgfate/60_member/member.php?appVer=1.55.0"
    )
    """国服状态接口"""
    fgo_data_url_jp: str = "https://game.fate-go.jp/gamedata/top?appVer=1.0.0"
    """日服状态接口"""


plugin_config = register(
    "fgo_server_status",
    Config,
    title="FGO 服务器状态",
    description="国服、日服维护状态的查询和推送",
    env=lambda: get_plugin_config(Config),
)
