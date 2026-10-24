"""对话相关的管理指令 /llm（仅超管）。

原先挂在 /ds 下面；/ds 并入通用对话后，单独拎出来管模型和官方机器人绑定。
"""

from nonebot.adapters import Bot, Event
from nonebot.adapters.qq.event import GroupMessageCreateEvent
from nonebot.permission import SUPERUSER
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    CommandMeta,
    Option,
    Query,
    Subcommand,
    SupportAdapter,
    on_alconna,
)
from nonebot_plugin_alconna.uniseg import get_target

from src.providers.llm import list_models

from .binding import GroupBinding, group_bindings
from .config import current_model, runtime

llm = on_alconna(
    Alconna(
        "llm",
        Subcommand(
            "model",
            Args["name?#模型别名", str],
            help_text="查看可用模型，或切换对话模型（LLM__MODELS 中的别名）",
        ),
        Subcommand(
            "bind",
            Args["openid?#群 openid", str],
            Option("-l|--list", dest="list", help_text="列出全部绑定"),
            Option(
                "-b|--bot",
                Args["bot#官方机器人 AppID", str],
                dest="bot",
                help_text="指定发送用的官方机器人 AppID",
            ),
            help_text="绑定本群与官方机器人的 group_openid，之后长回答走原生 markdown",
        ),
        Subcommand("unbind", help_text="解除本群的 group_openid 绑定"),
        meta=CommandMeta(
            description="对话模型与官方机器人绑定的管理",
            usage="/llm model [别名] | bind [openid] [-b AppID] | bind -l | unbind",
        ),
    ),
    permission=SUPERUSER,
    use_cmd_start=True,
    skip_for_unmatch=False,
    comp_config={"lite": True},
)


@llm.assign("model")
async def _(name: Query[str] = Query("model.name")):
    models = list_models()
    current = current_model()
    if not name.available:
        listing = "\n".join(
            f"- {model}（当前）" if model == current else f"- {model}"
            for model in models
        )
        await llm.finish(
            f"可用的模型：\n{listing}\n用 /llm model <别名> 切换"
            if models
            else f"LLM__MODELS 里没有注册模型，当前使用 {current}"
        )
    if name.result not in models:
        await llm.finish(f"没有叫 {name.result} 的模型，可选：{'、'.join(models)}")

    runtime.model = name.result
    runtime.save()
    await llm.finish(f"对话模型已切换为 {name.result}")


def _onebot_group_id(event: Event) -> str | None:
    """事件所在的 OneBot 群号，非 OneBot 群聊时为 None"""
    target = get_target(event)
    if target.private or target.adapter != SupportAdapter.onebot11:
        return None
    return target.id


@llm.assign("bind.list")
async def _():
    if not group_bindings.bindings:
        await llm.finish("尚无群绑定")

    await llm.finish(
        "已绑定的群：\n"
        + "\n".join(
            f"- {group_id} -> {binding.group_openid}"
            + (f"（AppID {binding.bot_id}）" if binding.bot_id else "")
            for group_id, binding in group_bindings.bindings.items()
        )
    )


@llm.assign("bind")
async def _(
    bot: Bot,
    event: Event,
    openid: Query[str] = Query("bind.openid"),
    bot_id: Query[str] = Query("bind.bot.bot"),
):
    # group_openid 只在官方机器人自己的事件里出现，先在这边回显给超管抄走
    if isinstance(event, GroupMessageCreateEvent):
        await llm.finish(
            f"本群的 group_openid：{event.group_openid}\n"
            f"官方机器人 AppID：{bot.self_id}\n"
            f"再到 OneBot 所在的同一个群里执行 "
            f"/llm bind {event.group_openid} -b {bot.self_id} 完成绑定"
        )

    group_id = _onebot_group_id(event)
    if group_id is None:
        await llm.finish("请在 OneBot 所在的 QQ 群内使用该指令")

    if not openid.available:
        if (binding := group_bindings.get(group_id)) is None:
            await llm.finish(
                f"群 {group_id} 尚未绑定\n"
                "用法：/llm bind <group_openid> [-b <AppID>]\n"
                "group_openid 可在官方机器人所在的同一个群里执行 /llm bind 获取"
            )
        await llm.finish(
            f"群 {group_id} 已绑定 {binding.group_openid}"
            + (f"（AppID {binding.bot_id}）" if binding.bot_id else "")
        )

    binding = GroupBinding(
        group_openid=openid.result,
        bot_id=bot_id.result if bot_id.available else None,
    )
    group_bindings.set(group_id, binding)
    await llm.finish(
        f"已绑定群 {group_id} -> {binding.group_openid}\n"
        "本群的长回答将改由官方机器人以原生 markdown 发出"
    )


@llm.assign("unbind")
async def _(event: Event):
    group_id = _onebot_group_id(event)
    if group_id is None:
        await llm.finish("请在 OneBot 所在的 QQ 群内使用该指令")
    if not group_bindings.remove(group_id):
        await llm.finish(f"群 {group_id} 未绑定")
    await llm.finish(f"已解除群 {group_id} 的绑定")


@llm.handle()
async def _():
    await llm.finish(
        "用法：\n"
        "/llm model [别名]  查看或切换对话模型\n"
        "/llm bind [openid] [-b AppID]  绑定官方机器人（-l 列出全部）\n"
        "/llm unbind  解除绑定"
    )
