from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from nonebot_plugin_alconna.uniseg import Image, Segment, Text

from src.plugins.bison.post.protocol import HTMLContentSupport
from src.plugins.bison.theme import Theme, ThemeRenderError
from src.plugins.bison.utils import is_pics_mergable, pic_merge, to_image

if TYPE_CHECKING:
    from src.plugins.bison.post import Post


class Ht2iTheme(Theme):
    """使用浏览器将文本渲染为图片

    HTML render Text To Image.
    需要安装`nonebot_plugin_htmlrender`插件
    """

    name: str = "ht2i"
    need_browser: bool = True

    async def _text_render(self, text: str):
        from nonebot_plugin_htmlrender import render_markdown

        try:
            return Image(raw=(await render_markdown(text, width=400)).data)
        except Exception as e:
            raise ThemeRenderError(f"渲染文本失败: {e}")

    async def render(self, post: "Post"):  # pyright: ignore[reportIncompatibleMethodOverride]
        md_text = ""

        md_text += f"## {post.title}\n\n" if post.title else ""

        if isinstance(post, HTMLContentSupport):
            content = await post.get_html_content()
        else:
            content = await post.get_content()
        md_text += content if len(content) < 500 else f"{content[:500]}..."
        md_text += "\n\n"
        if rp := post.repost:
            md_text += f"> 转发自 {f'**{rp.nickname}**' if rp.nickname else ''}:  \n"
            md_text += f"> {rp.title}  \n" if rp.title else ""
            if isinstance(rp, HTMLContentSupport):
                rp_content = await rp.get_html_content()
            else:
                rp_content = await rp.get_content()

            md_text += (
                ">  \n> " + rp_content
                if len(rp_content) < 500
                else f"{rp_content[:500]}..." + "  \n"
            )
        md_text += "\n\n"

        md_text += f"###### 来源: {post.platform.name} {post.nickname or ''}\n"

        msgs: list[Segment] = [await self._text_render(md_text)]

        urls: list[str] = []
        if rp and rp.url:
            urls.append(f"转发详情: {rp.url}")
        if post.url:
            urls.append(f"详情: {post.url}")

        if urls:
            msgs.append(Text("\n".join(urls)))

        pics_group: list[Sequence[str | bytes | Path | BytesIO]] = []
        if post.images:
            pics_group.append(post.images)
        if rp and rp.images:
            pics_group.append(rp.images)

        client = await post.platform.ctx.get_client_for_static()

        for pics in pics_group:
            if is_pics_mergable(pics):
                pics = await pic_merge(list(pics), client)
            msgs.extend(map(to_image, pics))

        return msgs
