"""用 QQ 官方机器人把回答以原生 markdown 发进群。

群聊命令是 OneBot 侧收到的，官方机器人那边没有可引用的 msg_id，所以这里发出去
的是**主动消息**：受官方的主动推送额度和频率限制，超额会被接口直接拒掉
（``ActionFailed``），调用方需要自己准备退路。

原生 markdown（``markdown.content``）要求机器人开通了对应权限，未开通时接口同样
报错。群消息也没有流式接口——官方文档在群消息接口里写明「群消息不支持流式参数」，
所以这里是攒完整段回答之后一次性发出。
"""

from nonebot import get_bots, logger
from nonebot.adapters.qq import Bot as QQBot
from nonebot.adapters.qq.models import MessageMarkdown

from .binding import GroupBinding

MARKDOWN_MSG_TYPE = 2
"""群消息的 msg_type：0 文本 / 1 图文 / 2 markdown / 3 ark / 4 embed / 7 富媒体"""


def get_qq_bots() -> list[QQBot]:
    return [bot for bot in get_bots().values() if isinstance(bot, QQBot)]


def resolve_bot(binding: GroupBinding) -> QQBot | None:
    """挑出该绑定对应的官方机器人。

    绑定里记了 AppID 就按 AppID 找；没记则只在唯一一个官方机器人在线时才敢用，
    多个在线时无从判断 group_openid 属于谁，交由调用方提示重新绑定。
    """
    bots = get_qq_bots()
    if binding.bot_id is not None:
        return next((bot for bot in bots if bot.self_id == binding.bot_id), None)
    return bots[0] if len(bots) == 1 else None


async def send_group_markdown(binding: GroupBinding, content: str) -> bool:
    """发送成功返回 True，没有可用的官方机器人或接口报错返回 False"""
    bot = resolve_bot(binding)
    if bot is None:
        logger.warning(
            f"群 {binding.group_openid} 绑定的官方机器人不可用"
            f"（AppID={binding.bot_id or '未指定'}），退回普通发送"
        )
        return False

    try:
        await bot.post_group_messages(
            group_openid=binding.group_openid,
            msg_type=MARKDOWN_MSG_TYPE,
            markdown=MessageMarkdown(content=content),
        )
    except Exception as e:
        logger.opt(exception=e).warning(
            f"官方机器人 {bot.self_id} 发送群 markdown 失败，退回普通发送"
        )
        return False

    return True
