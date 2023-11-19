import random

from nonebot_plugin_alconna import Alconna, on_alconna

from .constant import drinks, eatings

eat_matcher = on_alconna(
    Alconna("re:(今天|[早中午晚][上饭餐午]|早上|夜宵|今晚)吃(什么|啥|点啥)(帮助)?")
)
drink_matcher = on_alconna(
    Alconna("re:(今天|[早中午晚][上饭餐午]|早上|夜宵|今晚)喝(什么|啥|点啥)(帮助)?")
)


@eat_matcher.handle()
async def eat_handler():
    food_name = random.choice(eatings["basic_food"])

    await eat_matcher.finish(f"建议{food_name}")


@drink_matcher.handle()
async def drink_handler():
    brand_name: str = random.choice(list(drinks.keys()))
    drink_name: str = random.choice(drinks[brand_name])

    await drink_matcher.finish(f"建议{brand_name}的{drink_name}")
