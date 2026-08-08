"""Playwright 浏览器 provider。

统一管理浏览器实例：配置了 ``BROWSER_WS_ENDPOINT`` 时连接远程 Playwright Server，
否则本地启动 firefox，并在启动时按需下载浏览器。
"""

from nonebot import get_driver

from .browser import config as plugin_config
from .browser import get_browser as get_browser
from .browser import get_new_page as get_new_page
from .browser import get_proxy_settings as get_proxy_settings
from .config import Config as Config
from .installer import install_browser as install_browser

# 远程模式下浏览器由 Playwright Server 提供，本地不需要装
if plugin_config.browser_install and not plugin_config.browser_ws_endpoint:
    get_driver().on_startup(install_browser)
