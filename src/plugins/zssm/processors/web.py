from nonebot import get_plugin_config, logger

from src.plugins.zssm.config import Config
from src.providers.playwright import get_browser, get_proxy_settings

config = get_plugin_config(Config)


async def process_web_page(url: str) -> str | None:
    """处理网页内容

    Args:
        url: 网页URL

    Returns:
        Optional[str]: 网页内容, 失败时返回None
    """
    try:
        proxy = get_proxy_settings()
        logger.info(f"使用代理: {proxy}")
        browser = await get_browser()
        # 代理挂在 context 上而不是 browser 上：远程 connect() 不接受 launch 参数
        context = await browser.new_context(proxy=proxy)
        page = await context.new_page()

        try:
            await page.goto(url, timeout=60000)
        except Exception as e:
            logger.opt(exception=e).error(f"打开链接失败: {url}, 错误: {e}")
            await context.close()
            return None

        # 获取页面的内容
        page_content = await page.query_selector("html")
        content_text = None

        if page_content:
            content_text = await page_content.inner_text()

        await context.close()

        if content_text and len(content_text) > config.zssm_web_max_chars:
            logger.info(
                f"网页内容过长，已截取前{config.zssm_web_max_chars}个字符，"
                f"原长度: {len(content_text)}"
            )
            content_text = (
                content_text[: config.zssm_web_max_chars] + "\n...[内容过长已截断]"
            )

    except Exception as e:
        logger.opt(exception=e).error(f"处理网页失败: {url}, 错误: {e}")
        return None
    else:
        return content_text
