from nonebot.adapters import Event
from nonebot_plugin_alconna import (
    Alconna,
    AlconnaMatch,
    Args,
    Match,
    MultiVar,
    on_alconna,
)

from src.libs.memory import memory_store

remember_matcher = on_alconna(
    Alconna("记住", Args["items", MultiVar(str, "+")]),
    use_cmd_start=True,
)
forget_matcher = on_alconna(
    Alconna("忘记", Args["keywords", MultiVar(str, "+")]),
    use_cmd_start=True,
)
region_matcher = on_alconna(
    Alconna("设置地区", Args["region?", str]),
    use_cmd_start=True,
)
show_matcher = on_alconna(Alconna("我的记忆"), use_cmd_start=True)
clear_matcher = on_alconna(Alconna("清空记忆"), use_cmd_start=True)


@remember_matcher.handle()
async def remember_handler(event: Event, items: Match = AlconnaMatch("items")):
    added = memory_store.add_preferences(event.get_user_id(), items.result)
    if not added:
        await remember_matcher.finish("这些我已经记住过啦")
    await remember_matcher.finish("记住了：" + "、".join(added))


@forget_matcher.handle()
async def forget_handler(event: Event, keywords: Match = AlconnaMatch("keywords")):
    user_id = event.get_user_id()
    words = [word for word in keywords.result if word.strip()]

    replies = []
    profile = memory_store.get(user_id)
    if profile.region and (
        "地区" in words or any(word in profile.region for word in words)
    ):
        memory_store.set_region(user_id, None)
        replies.append(f"已忘记地区“{profile.region}”")

    if removed := memory_store.remove_preferences(user_id, words):
        replies.append("已忘记：" + "、".join(removed))

    await forget_matcher.finish("；".join(replies) if replies else "没有找到相关的记录")


@region_matcher.handle()
async def region_handler(event: Event, region: Match = AlconnaMatch("region")):
    if not region.available or not region.result.strip():
        await region_matcher.finish("请带上地区，例如“设置地区 广州”")
    memory_store.set_region(event.get_user_id(), region.result)
    await region_matcher.finish(f"记住了，你在{region.result.strip()}")


@show_matcher.handle()
async def show_handler(event: Event):
    profile = memory_store.get(event.get_user_id())
    if profile.is_empty:
        await show_matcher.finish(
            "还没有关于你的记录，可以用“记住 <内容>”和“设置地区 <地区>”告诉我你的喜好"
        )
    await show_matcher.finish(profile.describe())


@clear_matcher.handle()
async def clear_handler(event: Event):
    if memory_store.clear(event.get_user_id()):
        await clear_matcher.finish("已清空关于你的全部记忆")
    await clear_matcher.finish("本来就没有关于你的记录")
