"""把对话片段搭成 DeepSeek 网页版样式的页面，再交给 htmlrender 截图。

以前图片路径是「整段 markdown → GitHub 样式页面 → 截图」，工具调用只能压成
代码块，通篇一个调性。这里改成按语义搭页面：用户气泡、思维链的弱化区块、
联网搜索卡片（带网页来源列表）、回答正文，只有回答正文仍走 markdown 渲染。

配色与版式对齐 DeepSeek 官方网页版的浅色主题（蓝色气泡 + 灰调思维链 +
圆角来源卡片）。字体交给渲染端：Playwright 侧装了 Sarasa Gothic 与
Noto CJK/Emoji（见 docker/playwright/Dockerfile），本机预览时回落到系统字体。
"""

from collections.abc import Sequence
from functools import cache
from typing import TYPE_CHECKING

import jinja2
from markupsafe import Markup
from nonebot_plugin_htmlrender import render_html

from .render import katex_assets, markdown_css, markdown_fragment
from .transcript import AnswerSection, Section

if TYPE_CHECKING:
    from nonebot_plugin_htmlrender import RenderedImage

WIDTH = 560
"""页面宽度（CSS 像素），聊天版式比原来的 500 稍宽一点更舒展"""

_CSS = """
:root {
  --text: #1a1c1e;
  --muted: #9aa0a6;
  --dim: #6b7280;
  --line: #ececf0;
  --soft: #f7f8fa;
  --accent: #4d6bfe;
  --mono: "Sarasa Mono SC", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: #fff;
  color: var(--text);
  font-family: "Sarasa UI SC", "PingFang SC", "Microsoft YaHei",
    "Noto Sans CJK SC", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 15px;
  line-height: 1.75;
  -webkit-font-smoothing: antialiased;
}

.chat {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 20px 18px 24px;
}

.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.msg > * { max-width: 100%; }

/* 用户气泡 */
.bubble {
  max-width: 84%;
  padding: 9px 15px;
  background: #eff4ff;
  border-radius: 16px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

/* 思维链：一个弱化的旁支，不抢正文 */
.think { width: 100%; }
.think-head {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 11px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--soft);
  color: var(--dim);
  font-size: 12.5px;
}
.think-head .ic { width: 13px; height: 13px; color: var(--accent); }
.think-text {
  margin-top: 8px;
  padding-left: 13px;
  border-left: 2px solid var(--line);
  color: var(--muted);
  font-size: 13.5px;
  line-height: 1.85;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

/* 工具调用卡片 */
.tool {
  width: 100%;
  padding: 11px 13px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--soft);
}
.tool-head {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #3c4149;
  font-size: 13.5px;
  font-weight: 600;
}
.tool.failed .tool-head { color: #d94b4b; }
.tool-head .ic { color: var(--accent); }
.tool.failed .tool-head .ic { color: #d94b4b; }
.query {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 9px;
  padding: 3px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  color: #5b6270;
  font-size: 13px;
  overflow-wrap: anywhere;
}
.query .ic { width: 13px; height: 13px; color: #a3a9b3; }

.sources {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin: 9px 0 0;
  padding: 0;
  list-style: none;
}
.sources li {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
  line-height: 1.6;
}
.sources i {
  flex: none;
  width: 17px;
  height: 17px;
  border-radius: 50%;
  background: #e8edff;
  color: var(--accent);
  font-style: normal;
  font-size: 11px;
  line-height: 17px;
  text-align: center;
}
.sources .name { color: #2f343b; overflow-wrap: anywhere; }
.sources .site { color: #a3a9b3; font-size: 12px; white-space: nowrap; }

.kv { margin-top: 9px; }
.kv .k {
  display: block;
  margin-bottom: 3px;
  color: #a3a9b3;
  font-size: 12px;
}
.kv pre {
  margin: 0;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  color: #5b6270;
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.note {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 13px;
}
.note .ic { width: 14px; height: 14px; }

/* 线性图标：跟着所在文字取色 */
.ic { flex: none; width: 15px; height: 15px; }

/* 回答正文：沿用 GitHub 的 markdown 排版，字体与配色对齐本页 */
.answer.markdown-body {
  width: 100%;
  background: transparent;
  color: var(--text);
  font-family: inherit;
  font-size: 15px;
  line-height: 1.8;
}
.markdown-body > :first-child { margin-top: 0; }
.markdown-body > :last-child { margin-bottom: 0; }
.markdown-body a { color: var(--accent); }
.markdown-body h1, .markdown-body h2 { border-bottom: 0; padding-bottom: 0; }
.markdown-body blockquote { border-left-color: var(--line); color: var(--muted); }
.markdown-body code, .markdown-body pre { font-family: var(--mono); }
.markdown-body pre {
  padding: 12px 13px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--soft);
  font-size: 12.5px;
}
/* 截图没有滚动条：代码块与表格的长内容必须回绕，否则会被直接裁掉 */
.markdown-body pre,
.markdown-body pre > code {
  white-space: pre-wrap;
  word-break: break-word;
}
.markdown-body table { display: table; width: 100%; }
.markdown-body table td, .markdown-body table th { word-break: break-word; }
"""

_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <style>{{ css|safe }}</style>
</head>
<body>
  <main class="chat">
    {%- for s in sections %}
    {%- if s.kind == 'user' %}
    <div class="msg user"><div class="bubble">{{ s.text }}</div></div>
    {%- elif s.kind == 'thinking' %}
    <div class="msg"><div class="think">
      <div class="think-head">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="1.8" stroke-linejoin="round">
          <path d="M12 3.2l2 6.8 6.8 2-6.8 2-2 6.8-2-6.8-6.8-2 6.8-2z"/></svg>
        已深度思考
      </div>
      <div class="think-text">{{ s.text }}</div>
    </div></div>
    {%- elif s.kind == 'tool' %}
    <div class="msg"><div class="tool{% if s.failed %} failed{% endif %}">
      <div class="tool-head">
        {%- if s.sources %}
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="1.8" stroke-linecap="round">
          <circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17"/>
          <path d="M12 3.5c2.4 2.7 2.4 14.3 0 17M12 3.5c-2.4 2.7-2.4 14.3 0 17"/></svg>
        {%- else %}
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="1.8" stroke-linecap="round">
          <path d="M4 8h9M17.5 8H20M4 16h3M11.5 16H20"/>
          <circle cx="15" cy="8" r="2.2"/><circle cx="9" cy="16" r="2.2"/></svg>
        {%- endif %}
        {{ s.title }}
      </div>
      {%- if s.query %}
      <div class="query">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="1.8" stroke-linecap="round">
          <circle cx="11" cy="11" r="6"/><path d="M15.6 15.6L20 20"/></svg>
        {{ s.query }}
      </div>
      {%- endif %}
      {%- if s.sources %}
      <ol class="sources">
        {%- for src in s.sources %}
        <li><i>{{ loop.index }}</i><span class="name">{{ src.name }}</span>
          <span class="site">{{ src.site }}</span></li>
        {%- endfor %}
      </ol>
      {%- else %}
      {%- if s.args and not s.query %}
      <div class="kv"><span class="k">入参</span><pre>{{ s.args }}</pre></div>
      {%- endif %}
      {%- if s.result %}
      <div class="kv"><span class="k">结果</span><pre>{{ s.result }}</pre></div>
      {%- endif %}
      {%- endif %}
    </div></div>
    {%- elif s.kind == 'answer' %}
    <div class="msg"><div class="answer markdown-body">{{ s.text|md }}</div></div>
    {%- else %}
    <div class="msg"><div class="note">
      <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 4.5l8.5 15h-17z"/><path d="M12 10v4"/>
        <path d="M12 16.6h.01"/></svg>
      {{ s.label }}：{{ s.text }}
    </div></div>
    {%- endif %}
    {%- endfor %}
  </main>
  {{ extra|safe }}
</body>
</html>
"""


@cache
def _template() -> jinja2.Template:
    env = jinja2.Environment(autoescape=True)
    env.filters["md"] = lambda text: Markup(markdown_fragment(text))
    return env.from_string(_TEMPLATE)


def chat_html(sections: Sequence[Section]) -> str:
    """对话片段 → 完整 HTML 页面"""
    html = _template().render(sections=sections, css=markdown_css() + _CSS, extra="")
    # KaTeX 资源按需附加：先渲染一遍看正文里有没有公式
    if extra := katex_assets(html):
        html = _template().render(
            sections=sections, css=markdown_css() + _CSS, extra=extra
        )
    return html


async def render_chat(
    sections: Sequence[Section],
    *,
    fallback: str = "",
    width: int = WIDTH,
    device_pixel_ratio: float = 2.0,
) -> "RenderedImage":
    """渲染成图片；没有可展示的片段时退回渲染 ``fallback`` 正文"""
    return await render_html(
        chat_html(list(sections) or [AnswerSection(fallback)]),
        width=width,
        device_pixel_ratio=device_pixel_ratio,
    )
