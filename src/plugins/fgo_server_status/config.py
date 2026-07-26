from nonebot import get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    fgo_data_url_cn: str = (
        "http://line1-s1-bili-fate.bilibiligame.net"
        "/rongame_beta/rgfate/60_member/member.php?appVer=1.55.0"
    )
    fgo_data_url_jp: str = "https://game.fate-go.jp/gamedata/top?appVer=1.0.0"
    fgo_recv_groups: list[int] = []


plugin_config = get_plugin_config(Config)
