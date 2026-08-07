from nonebot import logger
from playwright.async_api import Browser, Error, Playwright, async_playwright

from .installer import install_browser

_browser: Browser | None = None
_playwright: Playwright | None = None


async def init(**kwargs) -> Browser:
    global _browser
    global _playwright
    _playwright = await async_playwright().start()
    try:
        _browser = await launch_browser(**kwargs)
    except Error:
        await install_browser()
        _browser = await launch_browser(**kwargs)
    return _browser


async def launch_browser(**kwargs) -> Browser:
    assert _playwright is not None, "Playwright 没有安装"
    logger.info("使用 firefox 启动")
    return await _playwright.firefox.launch(**kwargs)


async def get_browser(**kwargs) -> Browser:
    return _browser if _browser and _browser.is_connected() else await init(**kwargs)
