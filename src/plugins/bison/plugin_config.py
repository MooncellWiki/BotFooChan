from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict, Field

from src.providers.settings import register

PlatformName = str
ThemeName = str


class PlugConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_attribute_docstrings=True)

    bison_use_pic: bool = Field(
        default=False,
        description=(
            "发送消息时将所有文本转换为图片，防止风控，"
            "仅需要推送文转图可以为 platform 指定 theme"
        ),
    )
    bison_use_browser: bool = Field(
        default=False,
        description="是否使用环境中的浏览器",
        alias="bison_theme_use_browser",
    )
    bison_init_filter: bool = True
    bison_use_queue: bool = True
    bison_filter_log: bool = False
    bison_to_me: bool = True
    bison_skip_browser_check: bool = False
    bison_use_pic_merge: int = 0
    """多图片时启用图片合并转发（仅限群）

    0：不启用；1：首条消息单独发送，剩余照片合并转发；2 以及以上：所有消息全部合并转发
    """
    bison_resend_times: int = 0
    bison_proxy: str | None = Field(default=None, json_schema_extra={"restart": True})
    """抓取各平台时用的代理"""
    bison_ua: str = Field(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        description="默认UA",
        json_schema_extra={"restart": True, "multiline": True},
    )
    bison_show_network_warning: bool = True
    bison_platform_theme: dict[PlatformName, ThemeName] = {}


plugin_config = register(
    "bison",
    PlugConfig,
    title="Bison 订阅推送",
    description="各平台动态的订阅与推送",
    env=lambda: get_plugin_config(PlugConfig),
)
