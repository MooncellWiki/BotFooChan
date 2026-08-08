from datetime import datetime
from zoneinfo import ZoneInfo

from nonebot import logger
from nonebot.adapters import Event
from nonebot.matcher import Matcher
from nonebot_plugin_alconna import Alconna, on_alconna
from pydantic_ai.settings import ModelSettings

from src.providers.llm import create_agent, extract_content_and_thinking
from src.providers.user_memory import memory_store

from .config import get_endpoint, w2e_config

TZ = ZoneInfo("Asia/Shanghai")

INSTRUCTIONS = """\
你是群聊里的干饭参谋，负责给群友推荐这一餐吃什么、喝什么。
要求：
- 结合群友的地区（本地特色、当地常见的店）与喜好、忌口做推荐；画像信息缺失时自由发挥
- 结合当前时间判断餐段（早餐、午餐、晚餐、夜宵），推荐要应景
- 推荐要具体到菜品、店或饮品，并保持多样，不要总是推荐类似的东西
- 只推荐一样，回复以“建议”开头，一句话给出建议，可再补一小句理由
- 口语化中文，不要使用 Markdown、列表或额外的寒暄\
"""

NOT_CONFIGURED_REPLY = "推荐功能还没有配置 LLM，请联系机器人管理员"
FAILED_REPLY = "推荐服务开小差了，稍后再试试"

eat_matcher = on_alconna(
    Alconna("re:(今天|[早中午晚][上饭餐午]|夜宵|今晚)吃(什么|啥|点啥)(帮助)?"),
    use_cmd_start=True,
)
drink_matcher = on_alconna(
    Alconna("re:(今天|[早中午晚][上饭餐午]|夜宵|今晚)喝(什么|啥|点啥)(帮助)?"),
    use_cmd_start=True,
)


async def _recommend(event: Event, kind: str) -> str:
    """调用 LLM 结合用户记忆实时生成推荐"""
    endpoint = get_endpoint()
    if endpoint is None:
        return NOT_CONFIGURED_REPLY

    now = datetime.now(TZ)
    profile = memory_store.get(event.get_user_id())
    prompt = (
        f"群友说：{event.get_plaintext().strip()}\n"
        f"当前时间：{now:%Y-%m-%d %H:%M}（周{'一二三四五六日'[now.weekday()]}）\n"
        f"群友画像：\n{profile.describe()}\n"
        f"请给出这位群友本餐{kind}的建议。"
    )

    agent = create_agent(
        endpoint,
        instructions=INSTRUCTIONS,
        settings=ModelSettings(
            timeout=w2e_config.timeout, temperature=w2e_config.temperature
        ),
    )
    try:
        result = await agent.run(prompt)
    except Exception as e:
        logger.opt(exception=e).error("what2eat LLM 推荐失败")
        return FAILED_REPLY

    content, _ = extract_content_and_thinking(result)
    return content or FAILED_REPLY


@eat_matcher.handle()
async def eat_handler(event: Event, matcher: Matcher):
    await matcher.finish(await _recommend(event, "吃的"))


@drink_matcher.handle()
async def drink_handler(event: Event, matcher: Matcher):
    await matcher.finish(await _recommend(event, "喝的"))
