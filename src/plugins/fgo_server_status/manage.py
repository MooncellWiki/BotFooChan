from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.permission import SUPERUSER
from nonebot_plugin_alconna import Alconna, Args, Match, on_alconna

from .storage import load_recv_groups, save_recv_groups

USAGE = "用法：/维护推送 开启|关闭|列表 [群号]"

push_manage = on_alconna(
    Alconna("fgo_push", Args["action?", str]["group_id?", int]),
    aliases={"维护推送"},
    permission=SUPERUSER,
    priority=10,
    use_cmd_start=True,
)


def _resolve_group_id(event: Event, group_id: Match[int]) -> int | None:
    if group_id.available:
        return group_id.result
    if isinstance(event, GroupMessageEvent):
        return event.group_id
    return None


@push_manage.handle()
async def handle_push_manage(
    event: Event, action: Match[str], group_id: Match[int]
) -> None:
    if not action.available:
        await push_manage.finish(USAGE)

    groups = load_recv_groups()
    match action.result:
        case "开启":
            gid = _resolve_group_id(event, group_id)
            if gid is None:
                await push_manage.finish(
                    "请在目标群内使用，或指定群号：/维护推送 开启 <群号>"
                )
            if gid in groups:
                await push_manage.finish(f"群 {gid} 已在维护推送列表中")
            groups.append(gid)
            save_recv_groups(groups)
            await push_manage.finish(f"已开启群 {gid} 的维护推送")
        case "关闭":
            gid = _resolve_group_id(event, group_id)
            if gid is None:
                await push_manage.finish(
                    "请在目标群内使用，或指定群号：/维护推送 关闭 <群号>"
                )
            if gid not in groups:
                await push_manage.finish(f"群 {gid} 不在维护推送列表中")
            groups.remove(gid)
            save_recv_groups(groups)
            await push_manage.finish(f"已关闭群 {gid} 的维护推送")
        case "列表":
            if not groups:
                await push_manage.finish("维护推送列表为空")
            await push_manage.finish(
                "维护推送群列表：\n" + "\n".join(str(group) for group in groups)
            )
        case _:
            await push_manage.finish(USAGE)
