"""把解释结果连同参考的聊天记录、联网来源和用量统计拼成一条消息发出去。"""

from nonebot_plugin_alconna.uniseg import Reply, UniMessage

from src.providers.chat_history import HistoryWindow, format_record, format_records
from src.providers.llm import UsageTracker
from src.providers.llm.transcript import Source, ToolSection

from .processors.ai import ZssmAnswer


def render_context(window: HistoryWindow) -> str:
    """模型看过的聊天记录（预先附带的加上它自己翻的），被解释的那条用 👉 标出"""
    lines = [format_records(window.used(), with_seq=False)]
    if window.anchor is not None:
        lines.append(f"👉 {format_record(window.anchor, with_seq=False)}")
    return "\n".join(lines)


def render_searches(searches: list[ToolSection]) -> str:
    """搜索词与来源。

    模型常换个说法再搜一次，搜到的网页大半重复，所以来源合并去重后统一编号；
    链接单独成行，QQ 里才点得开。
    """
    lines = [
        f"🔍 {search.query or search.label}"
        + (f"（{search.failed}）" if search.failed else "")
        for search in searches
    ]
    sources: dict[str, Source] = {}
    for search in searches:
        for source in search.sources:
            sources.setdefault(source.url, source)
    if sources:
        lines.append("")
        lines.extend(
            f"{i}. {source.name}\n{source.url}"
            for i, source in enumerate(sources.values(), 1)
        )
    return "\n".join(lines)


async def send_answer(
    answer: ZssmAnswer,
    tracker: UsageTracker,
    window: HistoryWindow | None,
    reply_to: Reply | None,
) -> None:
    parts = [answer.text]
    if window is not None and window.seen:
        parts.append(render_context(window))
    if answer.searches:
        parts.append(render_searches(answer.searches))
    parts.append(tracker.render())
    await UniMessage.text("\n\n".join(parts)).send(reply_to=reply_to)
