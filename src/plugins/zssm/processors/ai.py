"""AI 响应生成（模型调用基于 pydantic-ai 统一封装）"""

from dataclasses import dataclass, field

from nonebot import get_plugin_config, logger
from pydantic import BaseModel
from pydantic_ai.messages import UserContent
from pydantic_ai.native_tools import WebSearchTool
from pydantic_ai.output import PromptedOutput
from pydantic_ai.settings import ModelSettings

from src.plugins.zssm.config import Config
from src.providers.chat_history import HistoryWindow
from src.providers.llm import UsageTracker, create_agent, resolve_endpoint
from src.providers.llm.transcript import ToolSection, build_sections

config = get_plugin_config(Config)

REQUEST_TIMEOUT = 120

BLOCKED_REPLY = "（抱歉，我现在还不会这个）"


class ZssmOutput(BaseModel):
    """prompt.txt 中约定的结构化输出"""

    output: str
    """输出内容"""
    keyword: list[str] | str | None = None
    """关键词"""
    block: bool = False
    """是否为无效内容"""


@dataclass
class ZssmAnswer:
    """一次解释的结果"""

    text: str
    """发给用户的回答，已拼上关键词"""
    searches: list[ToolSection] = field(default_factory=list)
    """联网搜索的记录：搜索词与搜到的网页来源"""


async def generate_ai_response(
    system_prompt: str,
    user_prompt: str | list[UserContent],
    tracker: UsageTracker,
    window: HistoryWindow | None = None,
) -> ZssmAnswer | None:
    """生成 AI 响应

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词, 带图片时为「正文 + 图片」的多模态输入
        tracker: 用量统计器, 记录本次调用的耗时与 token 消耗
        window: 聊天记录窗口, 传入时给模型挂上翻聊天记录的工具

    Returns:
        Optional[ZssmAnswer]: AI 生成的响应, 失败时返回 None
    """
    if not config.zssm_ai_model:
        return None
    endpoint = resolve_endpoint(config.zssm_ai_model)
    if endpoint is None:
        return None

    agent = create_agent(
        endpoint,
        instructions=system_prompt,
        output_type=PromptedOutput(ZssmOutput),
        settings=ModelSettings(timeout=REQUEST_TIMEOUT),
        retries=2,
        web_search=config.zssm_ai_web_search,
    )
    if window is not None:
        window.register(agent)

    logger.info(f"开始生成AI响应: {config.zssm_ai_model}")
    try:
        with tracker.stage("生成回答"):
            result = await agent.run(user_prompt)
    except Exception as e:
        logger.opt(exception=e).error("生成AI响应失败")
        return None

    tracker.record(endpoint.name, result)

    llm_output = result.output
    # 提示词约定无从解释时 block=true、output 留空；漏标 block 的也按此处理，
    # 免得发出去一句只有「关键词：」的空回答
    if llm_output.block or not llm_output.output.strip():
        return ZssmAnswer(BLOCKED_REPLY)

    if keywords := llm_output.keyword:
        if isinstance(keywords, list):
            keywords = " | ".join(keywords)
        response = f"关键词：{keywords}\n\n{llm_output.output}"
    else:
        response = llm_output.output

    # 联网搜索由服务商执行，调用与结果都留在消息记录里，按顺序拆出来就是搜索过程；
    # 翻聊天记录的工具调用另有窗口记着，这里只要联网搜索
    searches = [
        section
        for section in build_sections(result.new_messages())
        if isinstance(section, ToolSection) and section.name == WebSearchTool.kind
    ]
    return ZssmAnswer(response, searches)
