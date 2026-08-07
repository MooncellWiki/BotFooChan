"""这是什么？问一下！用 ai 来解释群友发送的「未知」内容

迁移自 nonebot-plugin-zssm (https://github.com/djkcyl/nonebot-plugin-zssm)
原作者 djkcyl，MIT License。
模型调用已改为基于 pydantic-ai 的统一封装（src/libs/llm）。
"""

from nonebot import get_driver, get_plugin_config, require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")

from .browser import install_browser
from .config import Config

__plugin_meta__ = PluginMetadata(
    name="zssm",
    description="这是什么？问一下！用 ai 来解释群友发送的「未知」内容",
    usage="对着任意你不懂的内容发送「zssm」即可",
    type="application",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
)


config = get_plugin_config(Config)
if config.zssm_install_browser:
    driver = get_driver()
    driver.on_startup(install_browser)

from . import handle as handle
