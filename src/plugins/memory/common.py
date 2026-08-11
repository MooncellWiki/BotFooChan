from nonebot import require
from nonebot.adapters import Event

require("nonebot_plugin_waiter")
require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import Alconna, on_alconna
from nonebot_plugin_waiter import prompt

from src.providers.user_memory import clear_memory, get_memory, set_memory

EDIT_TIMEOUT = 120
"""等待用户发来新档案的超时（秒）"""

EMPTY_REPLY = (
    "还没有关于你的记录。直接 @ 我聊天就行，聊到的偏好、忌口这些我会自己记下来"
)
CANCEL_WORDS = ("取消", "算了", "cancel")

show_matcher = on_alconna(Alconna("我的记忆"), use_cmd_start=True)
edit_matcher = on_alconna(Alconna("编辑记忆"), use_cmd_start=True)
clear_matcher = on_alconna(Alconna("清空记忆"), use_cmd_start=True)


@show_matcher.handle()
async def show_handler(event: Event):
    content = await get_memory(event.get_user_id())
    if not content:
        await show_matcher.finish(EMPTY_REPLY)
    await show_matcher.finish(f"我记得关于你的这些：\n{content}")


@edit_matcher.handle()
async def edit_handler(event: Event):
    """整份覆盖档案。

    档案是多行 markdown，让 alconna 按空白切分再拼回来会把换行吃掉，
    所以这里不收内联参数，改为等用户把新内容整条发过来。
    """
    user_id = event.get_user_id()
    current = await get_memory(user_id)

    resp = await prompt(
        (f"当前记录是：\n{current}\n\n" if current else "目前还没有记录。\n")
        + f"把修改后的完整内容发给我（{EDIT_TIMEOUT} 秒内），发“取消”放弃",
        timeout=EDIT_TIMEOUT,
    )
    if resp is None:
        await edit_matcher.finish("等太久了，这次就先不改了")

    content = resp.extract_plain_text().strip()
    if not content or content in CANCEL_WORDS:
        await edit_matcher.finish("那就不改了")

    saved = await set_memory(user_id, content)
    # 超长时 set_memory 会顺手压缩，存进去的未必是用户发来的原文
    if saved != content:
        await edit_matcher.finish(f"内容有点长，我压缩了一下再记住的：\n{saved}")
    await edit_matcher.finish("已更新")


@clear_matcher.handle()
async def clear_handler(event: Event):
    if await clear_memory(event.get_user_id()):
        await clear_matcher.finish("已清空关于你的全部记忆")
    await clear_matcher.finish("本来就没有关于你的记录")
