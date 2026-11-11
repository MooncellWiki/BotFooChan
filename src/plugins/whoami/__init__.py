"""/whoami：被 @ 的机器人回它认出来的群 id 和用户 id。

官方机器人眼里的群和人都是按 AppID 脱敏的 group_openid、member_openid，和群号、
QQ 号对不上。配 SUPERUSERS、/官q 时都得知道「这个机器人看我是谁」。只认真 @ 了
自己的那条（私聊不用 @），由被 @ 的机器人回，几个机器人在同一个群里也不会都回。
"""

from nonebot import require
from nonebot.adapters import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule

require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import (
    Alconna,
    CommandMeta,
    SupportAdapter,
    UniMsg,
    on_alconna,
)
from nonebot_plugin_alconna.uniseg import get_target

from src.providers.platform.mentions import mentions_bot

__plugin_meta__ = PluginMetadata(
    "我是谁",
    "@ 机器人查看它认出来的群 id 和用户 id",
    "@机器人 /whoami：由被 @ 的机器人回复本群 id、你的用户 id、是否超管（私聊不用 @）",
)

CHANNELS: dict[str, str] = {
    SupportAdapter.qq.value: "QQ 官方机器人",
    SupportAdapter.feishu.value: "飞书",
    SupportAdapter.discord.value: "Discord",
}
"""适配器名 -> 展示的渠道名"""


async def _called(bot: Bot, event: Event, msg: UniMsg) -> bool:
    """私聊，或者消息里明确 @ 了这个机器人（昵称开头、回复它都不算）"""
    try:
        # 规则检查时还没有「当前 bot」上下文，不传 bot 会直接抛
        if get_target(event, bot).private:
            return True
    except Exception:
        return False
    return mentions_bot(bot, event, msg)


whoami = on_alconna(
    Alconna("whoami", meta=CommandMeta(description="查看机器人认出来的群和用户 id")),
    aliases={"我是谁"},
    rule=Rule(_called),
    use_cmd_start=True,
)


@whoami.handle()
async def _(bot: Bot, event: Event) -> None:
    target = get_target(event)
    adapter = bot.adapter.get_name()
    lines = [f"渠道：{CHANNELS.get(adapter, adapter)} {bot.self_id}"]
    if target.private:
        lines.append("会话：私聊")
    elif target.parent_id and adapter == SupportAdapter.discord.value:
        lines.append(f"服务器：{target.parent_id}，频道：{target.id}")
    elif target.parent_id:  # QQ 频道：频道 id 在 parent_id，子频道在 id
        lines.append(f"频道：{target.parent_id}，子频道：{target.id}")
    else:
        lines.append(f"群：{target.id}")
    lines.append(f"用户：{event.get_user_id()}")
    lines.append(f"超管：{'是' if await SUPERUSER(bot, event) else '否'}")
    await whoami.finish("\n".join(lines))
