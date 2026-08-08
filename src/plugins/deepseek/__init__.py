"""接入 DeepSeek 模型的智能对话插件

迁移自 nonebot-plugin-deepseek (https://github.com/KomoriDev/nonebot-plugin-deepseek)
原作者 Komorebi <mute231010@gmail.com>，MIT License。
模型调用已改为基于 pydantic-ai 的统一封装（src/providers/llm）。
"""

from importlib.util import find_spec

from nonebot import require
from nonebot.params import Depends
from nonebot.permission import SuperUser
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_waiter")
require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
from arclet.alconna import config as alc_config
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    CommandMeta,
    Field,
    Match,
    MultiVar,
    Namespace,
    Option,
    Query,
    Subcommand,
    on_alconna,
)

from .config import Config, ds_config, json_config

if htmlrender_enable := find_spec("nonebot_plugin_htmlrender") is not None:
    require("nonebot_plugin_htmlrender")

from . import hook as hook
from .api import RequestException, query_balance
from .extension import CleanDocExtension, ParseExtension, ReplyMergeExtension
from .handler import DeepSeekHandler

__plugin_meta__ = PluginMetadata(
    name="DeepSeek",
    description="接入 DeepSeek 模型，提供智能对话与问答功能",
    usage="/deepseek -h",
    type="application",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
)


ns = Namespace("deepseek", disable_builtin_options=set())
alc_config.namespaces["deepseek"] = ns


def _model_completion() -> str:
    return f"请输入模型名，预期为：{ds_config.get_enable_models()} 其中之一"


deepseek = on_alconna(
    Alconna(
        "deepseek",
        Args["content?#内容", MultiVar("str")],
        Option(
            "--use-model",
            Args[
                "model#模型名称",
                ds_config.get_enable_models(),
                Field(completion=_model_completion),
            ],
            help_text="指定模型",
        ),
        Option("--with-context", help_text="启用多轮对话"),
        Option(
            "-r|--render|--render-markdown",
            dest="render",
            help_text="渲染 Markdown 为图片",
        ),
        Subcommand("--balance", help_text="查看余额"),
        Subcommand(
            "model",
            Option("-l|--list", help_text="支持的模型列表"),
            Option(
                "--set-default",
                Args[
                    "model#模型名称",
                    ds_config.get_enable_models(),
                    Field(completion=_model_completion),
                ],
                dest="set",
                help_text="设置默认模型",
            ),
            Option(
                "--render-markdown",
                Args[
                    "state#状态",
                    ["enable", "disable", "on", "off"],
                    Field(
                        completion=lambda: (
                            "请输入状态，预期为："
                            '["enable", "disable", "on", "off"] 其中之一'
                        )
                    ),
                ],
                help_text="启用 Markdown 转图片",
            ),
            help_text="模型相关设置",
        ),
        namespace=alc_config.namespaces["deepseek"],
        meta=CommandMeta(
            description=__plugin_meta__.description,
            usage=__plugin_meta__.usage,
        ),
    ),
    aliases={"ds"},
    use_cmd_start=True,
    skip_for_unmatch=False,
    comp_config={"lite": True},
    extensions=[ReplyMergeExtension, CleanDocExtension, ParseExtension],
)

deepseek.shortcut(
    "多轮对话", {"command": "deepseek --with-context", "fuzzy": True, "prefix": True}
)
deepseek.shortcut(
    "余额", {"command": "deepseek --balance", "fuzzy": False, "prefix": True}
)
deepseek.shortcut(
    "模型列表", {"command": "deepseek model --list", "fuzzy": False, "prefix": True}
)
deepseek.shortcut(
    "设置默认模型",
    {"command": "deepseek model --set-default", "fuzzy": True, "prefix": True},
)

if reasoning_model := next(
    (
        name
        for name in ds_config.get_enable_models()
        if "reasoner" in name or "r1" in name.lower() or name.endswith("-pro")
    ),
    None,
):
    deepseek.shortcut(
        "深度思考",
        {
            "command": f"deepseek --use-model {reasoning_model}",
            "fuzzy": True,
            "prefix": True,
        },
    )


@deepseek.assign("balance")
async def _(is_superuser: bool = Depends(SuperUser())):
    if not is_superuser:
        await deepseek.finish("该指令仅超管可用")
    try:
        balances = await query_balance(json_config.default_model)

        await deepseek.finish(
            "".join(
                f"""
                货币：{balance.currency}
                总的可用余额: {balance.total_balance}
                未过期的赠金余额: {balance.granted_balance}
                充值余额: {balance.topped_up_balance}
                """
                for balance in balances.balance_infos
            )
        )
    except (ValueError, RequestException) as e:
        await deepseek.finish(str(e))


@deepseek.assign("model.list")
async def _():
    model_list = "\n".join(
        f"- {model}（默认）" if model == json_config.default_model else f"- {model}"
        for model in ds_config.get_enable_models()
    )
    message = (
        f"支持的模型列表: \n{model_list}\n"
        "输入 `/deepseek [内容] --use-model [模型名]` 单次选择模型\n"
        "输入 `/deepseek model --set-default [模型名]` 设置默认模型"
    )
    await deepseek.finish(message)


@deepseek.assign("model.set")
async def _(
    is_superuser: bool = Depends(SuperUser()),
    model: Query[str] = Query("model.set.model"),
):
    if not is_superuser:
        await deepseek.finish("该指令仅超管可用")
    json_config.default_model = model.result
    json_config.save()
    await deepseek.finish(f"已设置默认模型为：{model.result}")


@deepseek.assign("model.render-markdown")
async def _(
    is_superuser: bool = Depends(SuperUser()),
    state: Query[str] = Query("model.render-markdown.state"),
):
    if not is_superuser:
        await deepseek.finish("该指令仅超管可用")
    if not htmlrender_enable:
        await deepseek.finish("Markdown 转图片功能暂不可用")

    json_config.enable_md_to_pic = state.result in ("enable", "on")
    state_desc = "开启" if json_config.enable_md_to_pic else "关闭"

    json_config.save()
    await deepseek.finish(f"已{state_desc} Markdown 转图片功能")


@deepseek.handle()
async def _(
    content: Match[tuple[str, ...]],
    model_name: Query[str] = Query("use-model.model"),
    render_option: Query[bool] = Query("render.value"),
    context_option: Query[bool] = Query("with-context.value"),
) -> None:
    if not model_name.available:
        model_name.result = json_config.default_model

    model = ds_config.get_model_config(model_name.result)
    if not render_option.available:
        render_option.result = json_config.enable_md_to_pic

    await DeepSeekHandler(
        model=model,
        is_to_pic=render_option.result and htmlrender_enable,
        is_contextual=context_option.available,
    ).handle(" ".join(content.result) if content.available else None)
