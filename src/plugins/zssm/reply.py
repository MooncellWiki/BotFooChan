"""把解释结果折叠进一条合并转发（聊天记录）发出去。

解释动辄几百字，再带上参考的聊天记录、联网来源和用量统计，直接发出去会刷屏；
收进合并转发后群里只占一张卡片，卡片预览里照样能看到每条的开头。每段内容单独
一个节点，节点昵称就当小标题用。

合并转发只有 QQ 号机器人（OneBot v11 的 send_group_forward_msg、Milky 的 forward
消息段）发得了，别的适配器发普通消息，接口报错时也退回普通消息。
"""

from nonebot import logger
from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import SupportAdapter
from nonebot_plugin_alconna.uniseg import (
    CustomNode,
    Reference,
    Reply,
    UniMessage,
    get_target,
)

from src.providers.chat_history import HistoryWindow, format_record, format_records
from src.providers.llm import UsageTracker
from src.providers.llm.transcript import Source, ToolSection

from .processors.ai import ZssmAnswer

FORWARD_ADAPTERS = frozenset({SupportAdapter.onebot11, SupportAdapter.milky})


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
    bot: Bot,
    event: Event,
    answer: ZssmAnswer,
    tracker: UsageTracker,
    window: HistoryWindow | None,
    reply_to: Reply | None,
) -> None:
    nodes = [("zssm", answer.text)]
    if window is not None and window.seen:
        nodes.append((f"参考上下文（{len(window.seen)} 条）", render_context(window)))
    if answer.searches:
        nodes.append(("联网搜索", render_searches(answer.searches)))
    nodes.append(("耗时与用量", tracker.render()))

    if get_target(event, bot).adapter in FORWARD_ADAPTERS:
        # 内容包成 Text 段而不是裸字符串：OneBot 会把字符串当 CQ 码解析，
        # 模型输出和网页标题里混进一段 [CQ:at,qq=all] 就真的 @ 全体了
        forward = Reference(
            nodes=[
                CustomNode(bot.self_id, name, UniMessage.text(content))
                for name, content in nodes
            ]
        )
        try:
            await UniMessage(forward).send()
        except Exception as e:
            logger.opt(exception=e).warning("合并转发发送失败，改发普通消息")
        else:
            return

    await UniMessage.text("\n\n".join(content for _, content in nodes)).send(
        reply_to=reply_to
    )
