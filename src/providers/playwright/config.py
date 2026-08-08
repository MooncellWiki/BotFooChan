from pydantic import BaseModel


class Config(BaseModel):
    browser_ws_endpoint: str | None = None
    """远程 Playwright Server 的 WS 地址；配置后不再本地启动/下载浏览器"""
    browser_proxy: str | None = None
    """浏览器访问外部页面时使用的代理地址"""
    browser_install: bool = True
    """本地模式下是否在启动时自动下载浏览器"""
