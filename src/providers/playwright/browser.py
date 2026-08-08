from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from nonebot import get_plugin_config, logger
from playwright.async_api import (
    Browser,
    Error,
    Page,
    Playwright,
    ProxySettings,
    async_playwright,
)
from yarl import URL

from .config import Config
from .installer import install_browser

config = get_plugin_config(Config)

_browser: Browser | None = None
_playwright: Playwright | None = None


async def init(**kwargs) -> Browser:
    global _browser
    global _playwright
    _playwright = await async_playwright().start()

    if config.browser_ws_endpoint:
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
    endpoint = config.browser_ws_endpoint
    assert endpoint, "未配置 browser_ws_endpoint"
    logger.info(f"连接远程 firefox: {endpoint}")
    return await _playwright.firefox.connect(endpoint, **kwargs)


async def launch_browser(**kwargs) -> Browser:
    assert _playwright is not None, "Playwright 没有安装"
    logger.info("使用 firefox 启动")
    return await _playwright.firefox.launch(**kwargs)


async def get_browser(**kwargs) -> Browser:
    return _browser if _browser and _browser.is_connected() else await init(**kwargs)


@asynccontextmanager
async def get_new_page(
    device_scale_factor: float = 2, **kwargs
) -> AsyncGenerator[Page]:
    """开一个新页面，用完连同 context 一起关掉

    代理挂在 context 上而不是 browser 上：远程 connect() 不接受 launch 参数
    """
    browser = await get_browser()
    context = await browser.new_context(
        device_scale_factor=device_scale_factor,
        proxy=get_proxy_settings(),
        **kwargs,
    )
    try:
        yield await context.new_page()
    finally:
        await context.close()


def get_proxy_settings() -> ProxySettings | None:
    """解析 BROWSER_PROXY 为 Playwright 的代理配置，未配置时返回 None"""
    if not config.browser_proxy:
        return None

    proxy_uri = URL(config.browser_proxy)
    proxy: ProxySettings = {
        "server": f"{proxy_uri.scheme}://{proxy_uri.host}:{proxy_uri.port}"
    }
    if proxy_uri.user:
        proxy["username"] = proxy_uri.user
    if proxy_uri.password:
        proxy["password"] = proxy_uri.password
    return proxy
