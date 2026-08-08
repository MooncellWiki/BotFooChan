from nonebot import get_plugin_config, logger
from playwright.async_api import Browser, Error, Playwright, async_playwright

from src.plugins.zssm.config import Config

from .installer import install_browser

config = get_plugin_config(Config)

_browser: Browser | None = None
_playwright: Playwright | None = None


async def init(**kwargs) -> Browser:
    global _browser
    global _playwright
    _playwright = await async_playwright().start()

    if config.zssm_browser_ws_endpoint:
        _browser = await connect_browser(**kwargs)
        return _browser

    try:
        _browser = await launch_browser(**kwargs)
    except Error:
        await install_browser()
        _browser = await launch_browser(**kwargs)
    return _browser


async def connect_browser(**kwargs) -> Browser:
    assert _playwright is not None, "Playwright 没有安装"
    endpoint = config.zssm_browser_ws_endpoint
    assert endpoint, "未配置 zssm_browser_ws_endpoint"
    logger.info(f"连接远程 firefox: {endpoint}")
    return await _playwright.firefox.connect(endpoint, **kwargs)


async def launch_browser(**kwargs) -> Browser:
    assert _playwright is not None, "Playwright 没有安装"
    logger.info("使用 firefox 启动")
    return await _playwright.firefox.launch(**kwargs)


async def get_browser(**kwargs) -> Browser:
    return _browser if _browser and _browser.is_connected() else await init(**kwargs)
