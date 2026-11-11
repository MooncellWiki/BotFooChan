"""对话相关的管理指令 /llm（仅超管）。

原先挂在 /ds 下面；/ds 并入通用对话后单独拎了出来。官方机器人的群号绑定原先也在
这里（/llm bind），推送也要用它，挪到了 /官q 绑定。

切换模型改的是配置段 chat 的 model，和管理后台「模型路由」页改的是同一个值。
"""

from nonebot.adapters import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    CommandMeta,
    Query,
    Subcommand,
    on_alconna,
)

from src.providers.llm import list_models
from src.providers.settings import NotPersistentError, patch

from .config import current_model

llm = on_alconna(
    Alconna(
        "llm",
        Subcommand(
            "model",
            Args["name?#模型别名", str],
            help_text="查看可用模型，或切换对话模型（模型注册表里的别名）",
        ),
        meta=CommandMeta(
            description="对话模型的管理",
            usage="/llm model [别名]",
        ),
    ),
    permission=SUPERUSER,
    use_cmd_start=True,
    skip_for_unmatch=False,
    comp_config={"lite": True},
)


@llm.assign("model")
async def _(bot: Bot, event: Event, name: Query[str] = Query("model.name")):
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
            else f"模型注册表里没有模型，当前使用 {current}"
        )
    if name.result not in models:
        await llm.finish(f"没有叫 {name.result} 的模型，可选：{'、'.join(models)}")

    try:
        await patch(
            "chat",
            {"model": name.result},
            actor=f"{bot.adapter.get_name()}:{event.get_user_id()}",
        )
    except NotPersistentError as e:
        await llm.finish(f"切换失败：{e}")
    await llm.finish(f"对话模型已切换为 {name.result}")


@llm.handle()
async def _():
    await llm.finish(
        "用法：/llm model [别名]  查看或切换对话模型\n"
        "（官方机器人的群号绑定已挪到 /官q 绑定）"
    )
