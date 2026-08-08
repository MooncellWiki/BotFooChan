from typing import Any, ClassVar

from httpx import AsyncClient

from src.plugins.bison.post import Post
from src.plugins.bison.types import RawPost, Target
from src.plugins.bison.utils import anonymous_site

from .platform import NewMessage


class FF14(NewMessage):
    categories: ClassVar[dict] = {}
    platform_name = "ff14"
    name = "最终幻想XIV官方公告"
    enable_tag = False
    enabled = True
    is_common = False
    scheduler_class = "ff14"
    site = anonymous_site("interval", {"seconds": 60})
    has_target = False

    @classmethod
    async def get_target_name(cls, client: AsyncClient, target: Target) -> str | None:
        return "最终幻想XIV官方公告"

    async def get_sub_list(self, target: Target) -> list[RawPost]:
        client = await self.ctx.get_client()
        raw_data = await client.get(
            "https://cqnews.web.sdo.com/api/news/newsList?gameCode=ff&CategoryCode=5309,5310,5311,5312,5313&pageIndex=0&pageSize=5"
        )
        return raw_data.json()["Data"]

    def get_id(self, post: RawPost) -> Any:
        """用发布时间当作 ID

        因为有时候官方会直接编辑以前的文章内容
        """
        return post["PublishDate"]

    def get_date(self, post: RawPost) -> None:
        return None

    async def parse(self, raw_post: RawPost) -> Post:
        title = raw_post["Title"]
        text = raw_post["Summary"]
        url = raw_post["Author"]
        return Post(
            self, content=text, title=title, url=url, nickname="最终幻想XIV官方公告"
        )
