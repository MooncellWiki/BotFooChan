from bs4 import BeautifulSoup
from httpx import AsyncClient

from ..registry import registry

headers = {
    "User-Agent": "Firefox/90.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0"  # noqa: E501
}


@registry.register()
async def get_web_content(url: str):
    """通过链接获取网页内容

    参数:
        url: 网页链接
    """

    async with AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            return "获取网页内容失败：" + str(response.status_code)

        soup = BeautifulSoup(response.text, "html.parser")

    return soup.get_text()
