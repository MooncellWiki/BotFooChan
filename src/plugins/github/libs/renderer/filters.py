from dataclasses import asdict
from datetime import UTC, datetime

import humanize
from markdown_it import MarkdownIt
from markdown_it.renderer import RendererProtocol
from markdown_it.token import Token
from markdown_it.utils import OptionsDict
from mdit_py_emoji import emoji_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from nonebot import logger

from .context import TimelineEvent

REVIEW_STATES = {
    "commented": "reviewed",
    "changes_requested": "requested changes",
    "approved": "approved these changes",
}
"""Review state / render text mapping"""

title_md = MarkdownIt("zero").enable("backticks").use(emoji_plugin, shortcuts={})
"""Markdown parser for issue/pr title"""
emoji_md = MarkdownIt("zero").use(emoji_plugin, shortcuts={})
"""Markdown parser for emoji"""
gfm_md = MarkdownIt("gfm-like").use(tasklists_plugin).use(emoji_plugin, shortcuts={})
"""Markdown parser for gfm-like markdown"""


def emoji_format(
    renderer: RendererProtocol,
    tokens: list[Token],
    idx: int,
    options: OptionsDict,
    env: dict,
) -> str:
    """Render emoji token to html"""
    return (
        f'<g-emoji class="g-emoji" alias="{tokens[idx].markup}">'
        f"{tokens[idx].content}"
        "</g-emoji>"
    )


title_md.add_render_rule("emoji", emoji_format)
emoji_md.add_render_rule("emoji", emoji_format)


def markdown_title(text: str) -> str:
    """Render issue/pr title"""
    return title_md.renderInline(text)


def markdown_emoji(text: str) -> str:
    """Render emoji text"""
    return emoji_md.renderInline(text)


def markdown_gfm(text: str) -> str:
    """Render gfm-like markdown"""
    return gfm_md.render(text)


def relative_time(value: datetime | str) -> str:
    """Humanize relative datetime"""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not value.tzinfo:
        value = value.replace(tzinfo=UTC)
    now = datetime.now(value.tzinfo)
    delta = now - value
    if delta.microseconds > 0 and delta.days < 30:
        return humanize.naturaltime(delta)

    t = "%d %b" if value.year == now.year else "%d %b %Y"
    return f"on {humanize.naturalday(value, t)}"


def debug_event(event: TimelineEvent) -> str:
    """Log unhandled event using error level to report on sentry"""
    event_data = asdict(event)
    logger.debug(f"Unhandled event: {event_data}")
    logger.error(
        "Unhandled event type: {event_type}",
        event_type=f"{event.__class__.__name__}"
        + (f" {event_name}" if (event_name := getattr(event, "event", None)) else ""),
        event=event_data,
    )
    return ""


def review_state(value: str) -> str:
    """Render review state to text"""
    return REVIEW_STATES.get(value, value)


def left_truncate(value: str, max_length: int) -> str:
    """Truncate string from left"""
    return f"...{value[-max_length:]}" if len(value) > max_length else value
