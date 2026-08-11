"""把一次运行产生的消息拆成结构化的对话片段。

以前只发最终正文，模型中途做了什么（目前主要是服务商内置的联网搜索）全被丢掉，
群里只能看到凭空冒出的结论。这里按 ``result.new_messages()`` 的原始顺序拆出
用户提问、思维链、工具调用、回答，交给两套渲染：

- :mod:`.chat` 把片段搭成 DeepSeek 网页版样式的页面再截图（图片路径）
- 本模块的 :func:`render_transcript` 拍平成纯文本或基础 markdown
  （QQ 官方原生 markdown 与纯文本路径都没有排版能力）

工具的入参与结果保留原始 JSON（截断后展示），联网搜索一类会额外抽出网页来源，
让渲染层能摆成来源列表而不是一坨 JSON。
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
import json
from typing import Any, ClassVar, Literal
from urllib.parse import urlparse

from pydantic_ai.messages import (
    BaseToolCallPart,
    BaseToolReturnPart,
    FilePart,
    ModelMessage,
    RetryPromptPart,
    TextContent,
    TextPart,
    ThinkingPart,
    UserPromptPart,
)

from src.providers.llm import split_inline_thinking, thinking_text

Flavor = Literal["markdown", "text"]

MAX_TOOL_ARGS = 400
"""工具入参的最大展示长度（字符）"""
MAX_TOOL_RESULT = 600
"""工具结果的最大展示长度（字符）；联网搜索的结果动辄上千字"""
MAX_SOURCES = 8
"""最多展示的网页来源条数"""

_TOOL_ALIASES = {
    "web_search": "联网搜索",
    "web_fetch": "网页读取",
    "url_context": "网页读取",
    "file_search": "文件检索",
    "tool_search": "工具检索",
    "code_execution": "代码执行",
    "image_generation": "图片生成",
    "memory": "记忆",
}
"""服务商内置工具的中文名，未收录的直接显示原始工具名"""

_OUTCOMES = {
    "failed": "失败",
    "denied": "已拒绝",
    "interrupted": "已中断",
}


@dataclass
class Source:
    """工具结果里带出的网页来源"""

    url: str
    title: str = ""

    @property
    def site(self) -> str:
        return urlparse(self.url).netloc.removeprefix("www.")

    @property
    def name(self) -> str:
        return self.title or self.site or self.url


@dataclass
class UserSection:
    text: str
    kind: ClassVar[str] = "user"


@dataclass
class ThinkingSection:
    text: str
    kind: ClassVar[str] = "thinking"


@dataclass
class AnswerSection:
    text: str
    """markdown 正文"""
    kind: ClassVar[str] = "answer"


@dataclass
class ToolSection:
    name: str
    """原始工具名"""
    args: str = ""
    result: str = ""
    query: str = ""
    """检索类工具的关键词，从入参里抽出来单独展示"""
    sources: list[Source] = field(default_factory=list)
    outcome: str = "success"
    kind: ClassVar[str] = "tool"

    @property
    def label(self) -> str:
        return _TOOL_ALIASES.get(self.name, self.name)

    @property
    def failed(self) -> str:
        """非成功结局的中文描述，成功时为空串"""
        return _OUTCOMES.get(self.outcome, "")

    @property
    def title(self) -> str:
        if self.failed:
            return f"{self.label}（{self.failed}）"
        if self.sources:
            return f"已搜索到 {len(self.sources)} 个网页"
        return self.label


@dataclass
class NoteSection:
    """重试提示、附件占位一类的旁白"""

    label: str
    text: str
    kind: ClassVar[str] = "note"


Section = UserSection | ThinkingSection | AnswerSection | ToolSection | NoteSection


def build_sections(
    messages: Sequence[ModelMessage], *, with_thinking: bool = False
) -> list[Section]:
    """按消息顺序拆出对话片段"""
    sections: list[Section] = []
    calls: dict[str, ToolSection] = {}
    """tool_call_id -> 调用片段，结果回填到同一段里，避免调用与结果分成两块"""

    for message in messages:
        for part in message.parts:
            # 人设（SystemPromptPart / InstructionPart）不展示
            if isinstance(part, UserPromptPart):
                if text := _user_text(part):
                    sections.append(UserSection(text))

            elif isinstance(part, ThinkingPart):
                if with_thinking and (text := thinking_text(part).strip()):
                    sections.append(ThinkingSection(text))

            elif isinstance(part, TextPart):
                # 部分中转服务不拆分思维链，直接内联在正文里
                content, inline = split_inline_thinking(part.content)
                if with_thinking and inline:
                    sections.append(ThinkingSection(inline))
                if content:
                    sections.append(AnswerSection(content))

            elif isinstance(part, BaseToolCallPart):
                args = part.args_as_dict() if part.has_content() else {}
                section = ToolSection(
                    name=part.tool_name,
                    args=_truncate(_format_args(part), MAX_TOOL_ARGS),
                    query=_query_of(args),
                )
                sections.append(section)
                calls[part.tool_call_id] = section

            elif isinstance(part, BaseToolReturnPart):
                section = calls.pop(part.tool_call_id, None)
                if section is None:
                    section = ToolSection(part.tool_name)
                    sections.append(section)
                section.outcome = part.outcome
                section.sources = _collect_sources(
                    part.content_items(mode="jsonable", wrap_if_error=False)
                )
                section.result = _truncate(_format_result(part), MAX_TOOL_RESULT)

            elif isinstance(part, RetryPromptPart):
                text = _truncate(part.model_response(), MAX_TOOL_RESULT)
                sections.append(NoteSection("重试", text))

            elif isinstance(part, FilePart):
                sections.append(NoteSection("附件", part.content.media_type))

    return sections


def render_transcript(
    sections: Sequence[Section],
    *,
    flavor: Flavor = "markdown",
    fallback: str = "",
) -> str:
    """把片段拍平成一段文本；没有任何可展示内容时返回 ``fallback``"""
    if not sections:
        return fallback
    render = _markdown_section if flavor == "markdown" else _text_section
    return "\n\n".join(render(section) for section in sections)


def _user_text(part: UserPromptPart) -> str:
    if isinstance(part.content, str):
        return part.content.strip()

    chunks: list[str] = []
    for item in part.content:
        if isinstance(item, str):
            chunks.append(item)
        elif isinstance(item, TextContent):
            chunks.append(item.content)
        else:
            chunks.append(f"（{type(item).__name__}）")
    return "\n".join(chunks).strip()


def _query_of(args: dict[str, Any]) -> str:
    """检索类工具的关键词。各家字段名不一，取常见的几个"""
    for key in ("query", "queries", "q", "search_query"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list) and value:
            return " / ".join(str(item) for item in value)
    return ""


def _collect_sources(value: object, depth: int = 0) -> list[Source]:
    """递归捞出结果里的网页来源。

    OpenAI Responses 放在 ``{"sources": [{"url", "title"}]}``，Anthropic 直接是
    ``[{"type": "web_search_result", "url", "title"}]``，形状不统一，
    干脆认「带 url 的对象」。
    """
    if depth > 4:
        return []

    sources: list[Source] = []
    if isinstance(value, dict):
        url = value.get("url")
        if isinstance(url, str) and url.startswith("http"):
            title = value.get("title")
            sources.append(Source(url, title if isinstance(title, str) else ""))
        else:
            for item in value.values():
                sources.extend(_collect_sources(item, depth + 1))
    elif isinstance(value, list):
        for item in value:
            sources.extend(_collect_sources(item, depth + 1))

    seen: set[str] = set()
    unique = [s for s in sources if not (s.url in seen or seen.add(s.url))]
    return unique[:MAX_SOURCES]


def _format_args(part: BaseToolCallPart) -> str:
    if not part.has_content():
        return ""
    if isinstance(part.args, str):
        return _prettify(part.args)
    return _dump(part.args)


def _format_result(part: BaseToolReturnPart) -> str:
    chunks = [
        _prettify(item) if isinstance(item, str) else f"（{type(item).__name__}）"
        for item in part.content_items(mode="str")
    ]
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def _dump(value: object) -> str:
    # 不做缩进：截断额度有限，缩进只会挤掉真正有用的内容
    return json.dumps(value, ensure_ascii=False)


def _prettify(text: str) -> str:
    """规整 JSON 形式的入参/结果，非 JSON 原样返回"""
    try:
        value = json.loads(text)
    except ValueError:
        return text.strip()
    return _dump(value) if isinstance(value, dict | list) else text.strip()


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}…（已截断）"


def _markdown_section(section: Section) -> str:
    match section:
        case UserSection():
            return f"**🧑 用户**\n\n{section.text}"
        case ThinkingSection():
            return f"**💭 思考**\n\n{_quote(section.text)}"
        case AnswerSection():
            return f"**🤖 回答**\n\n{section.text}"
        case NoteSection():
            return f"**⚠️ {section.label}**\n\n{section.text}"
        case ToolSection():
            lines = [f"**🔧 {section.title}**"]
            if section.query:
                lines.append(f"搜索：{section.query}")
            if section.sources:
                lines.append(
                    "\n".join(
                        f"{i}. {s.name} － {s.site}"
                        for i, s in enumerate(section.sources, 1)
                    )
                )
            else:
                lines.extend(_tool_details(section))
            return "\n\n".join(lines)


def _text_section(section: Section) -> str:
    match section:
        case UserSection():
            return f"【🧑 用户】\n{section.text}"
        case ThinkingSection():
            return f"【💭 思考】\n{section.text}"
        case AnswerSection():
            return f"【🤖 回答】\n{section.text}"
        case NoteSection():
            return f"【⚠️ {section.label}】\n{section.text}"
        case ToolSection():
            lines = [f"【🔧 {section.title}】"]
            if section.query:
                lines.append(f"搜索：{section.query}")
            if section.sources:
                lines.extend(
                    f"{i}. {s.name} － {s.site}"
                    for i, s in enumerate(section.sources, 1)
                )
            else:
                lines.extend(
                    line.replace("```json\n", "").replace("\n```", "")
                    for line in _tool_details(section)
                )
            return "\n".join(lines)


def _tool_details(section: ToolSection) -> list[str]:
    """没有来源可展示时，退回入参与结果的原始 JSON"""
    details: list[str] = []
    if section.args and not section.query:
        details.append(f"入参\n```json\n{section.args}\n```")
    if section.result:
        details.append(f"结果\n```json\n{section.result}\n```")
    return details


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())
