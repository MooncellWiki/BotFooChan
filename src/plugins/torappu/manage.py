import httpx
from nonebot import logger
from nonebot.permission import SUPERUSER
from nonebot_plugin_alconna import Alconna, Args, Match, Option, on_alconna

from .config import plugin_config
from .data_source import launch_container, list_versions
from .utils import call_api, find_version

USAGE = "用法：/重跑 [版本] [上一版本] [--include 路径] [--exclude 路径]"

relaunch = on_alconna(
    Alconna(
        "torappu_launch",
        Args["version?", str]["prev_version?", str],
        Option("--include", Args["include_path", str]),
        Option("--exclude", Args["exclude_path", str]),
    ),
    aliases={"重跑"},
    permission=SUPERUSER,
    priority=10,
    use_cmd_start=True,
)


@relaunch.handle()
async def handle_relaunch(
    version: Match[str],
    prev_version: Match[str],
    include_path: Match[str],
    exclude_path: Match[str],
) -> None:
    if not plugin_config.torappu_auth_token:
        await relaunch.finish("未配置 TORAPPU_AUTH_TOKEN，无法发起重跑")

    versions = await call_api(relaunch, list_versions())

    if version.available:
        index = find_version(versions, version.result)
        if index is None:
            await relaunch.finish(f"未找到版本：{version.result}\n{USAGE}")
    else:
        if not versions:
            await relaunch.finish("版本列表为空，无法发起重跑")
        index = len(versions) - 1

    target = versions[index]

    if prev_version.available:
        prev_index = find_version(versions, prev_version.result)
        if prev_index is None:
            await relaunch.finish(f"未找到版本：{prev_version.result}\n{USAGE}")
        prev = versions[prev_index]
    elif index > 0:
        prev = versions[index - 1]
    else:
        await relaunch.finish(f"版本 {target['resVersion']} 没有上一版本，请手动指定")

    try:
        result = await launch_container(
            target["clientVersion"],
            target["resVersion"],
            prev["clientVersion"],
            prev["resVersion"],
            include_path.result if include_path.available else None,
            exclude_path.result if exclude_path.available else None,
        )
    except httpx.HTTPStatusError as e:
        logger.opt(colors=True, exception=e).error("发起 torappu 重跑出错")
        await relaunch.finish(
            f"发起重跑失败（HTTP {e.response.status_code}）：\n{e.response.text}"
        )
    except httpx.HTTPError as e:
        logger.opt(colors=True, exception=e).error("发起 torappu 重跑出错")
        await relaunch.finish(f"发起重跑失败，请稍后重试：\n{e!r}")

    await relaunch.finish(
        "已发起重跑：\n"
        f"{prev['clientVersion']} / {prev['resVersion']}\n"
        f"→ {target['clientVersion']} / {target['resVersion']}\n"
        f"容器：{result['container_name']}\n"
        f"状态：{result['status']}"
    )
