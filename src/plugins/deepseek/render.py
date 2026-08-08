"""deepseek 专用的 markdown 渲染，替代 htmlrender 内置的 Python-Markdown 管线。

htmlrender 的 render_markdown 用 Python-Markdown 转 HTML，不遵循 CommonMark：
列表前必须有空行、嵌套列表要求 4 空格缩进，LLM 输出经常整段糊成一个 <p>。
这里改用 markdown-it-py（CommonMark + 表格/删除线/任务列表）自己转 HTML，
页面模板、GitHub 样式和 KaTeX 资源直接复用 htmlrender 包内文件，
最后仍走它公开的 render_html 接口截图。
"""

from functools import cache
from importlib.resources import files
from typing import TYPE_CHECKING

import jinja2
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from mdit_py_plugins.texmath import texmath_plugin
from nonebot_plugin_htmlrender import render_html
from pygments import highlight as pygments_highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

if TYPE_CHECKING:
    from markdown_it.token import Token
    from markdown_it.utils import EnvType, OptionsDict
    from nonebot_plugin_htmlrender import RenderedImage

_MARKDOWN_TEMPLATES = files("nonebot_plugin_htmlrender") / "templates" / "markdown"


@cache
def _asset(name: str) -> str:
    return (_MARKDOWN_TEMPLATES / name).read_text(encoding="utf-8")


@cache
def _page_template() -> jinja2.Template:
    return jinja2.Environment(autoescape=True).from_string(_asset("markdown.html"))


def _render_fence(
    self: object,
    tokens: "list[Token]",
    idx: int,
    options: "OptionsDict",
    env: "EnvType",
) -> str:
    # pygments-default.css 的选择器都挂在 .codehilite 下，
    # 输出结构与 Python-Markdown codehilite 保持一致
    token = tokens[idx]
    lang = token.info.strip().split(maxsplit=1)[0] if token.info.strip() else "text"
    try:
        lexer = get_lexer_by_name(lang)
    except ClassNotFound:
        lexer = get_lexer_by_name("text")
    return pygments_highlight(
        token.content, lexer, HtmlFormatter(cssclass="codehilite")
    )


def _render_math_inline(
    self: object,
    tokens: "list[Token]",
    idx: int,
    options: "OptionsDict",
    env: "EnvType",
) -> str:
    # KaTeX 通过 mathtex-script-type.min.js 消费 math/tex script 标签，
    # 内容必须保持原始 TeX（浏览器不会解码 script 里的 HTML 实体）
    return f'<script type="math/tex">{tokens[idx].content}</script>'


def _render_math_block(
    self: object,
    tokens: "list[Token]",
    idx: int,
    options: "OptionsDict",
    env: "EnvType",
) -> str:
    return f'<script type="math/tex; mode=display">{tokens[idx].content}</script>\n'


@cache
def _parser() -> MarkdownIt:
    md = (
        MarkdownIt("commonmark", {"html": True})
        .enable("table")
        .enable("strikethrough")
        .use(tasklists_plugin)
        # dollarmath 负责 $..$/$$..$$，texmath 负责 \(..\)/\[..\]
        .use(dollarmath_plugin, double_inline=True)
        .use(texmath_plugin, delimiters="brackets")
    )
    md.add_render_rule("fence", _render_fence)
    md.add_render_rule("math_inline", _render_math_inline)
    for rule in (
        "math_inline_double",
        "math_block",
        "math_block_label",
        "math_block_eqno",
    ):
        md.add_render_rule(rule, _render_math_block)
    return md


def markdown_to_html(markdown_text: str) -> str:
    """CommonMark 语义的 markdown → 完整 HTML 页面。"""
    body = _parser().render(markdown_text)
    extra = ""
    if "math/tex" in body:
        extra = (
            f'<style type="text/css">{_asset("katex/katex.min.b64_fonts.css")}</style>'
            f"<script defer>{_asset('katex/katex.min.js')}</script>"
            f"<script defer>{_asset('katex/mhchem.min.js')}</script>"
            f"<script defer>{_asset('katex/mathtex-script-type.min.js')}</script>"
        )
    css = _asset("github-markdown-light.css") + _asset("pygments-default.css")
    return _page_template().render(md=body, css=css, extra=extra)


async def render_markdown(
    markdown_text: str,
    *,
    width: int = 500,
    device_pixel_ratio: float = 2.0,
) -> "RenderedImage":
    """与 htmlrender.render_markdown 同形的替代实现，默认宽度保持一致。"""
    return await render_html(
        markdown_to_html(markdown_text),
        width=width,
        device_pixel_ratio=device_pixel_ratio,
    )
