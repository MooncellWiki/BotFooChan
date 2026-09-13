"""图片内容识别（视觉模型调用基于 pydantic-ai 统一封装）"""

from nonebot import get_plugin_config, logger
from nonebot_plugin_alconna.uniseg import Image
from pydantic_ai.settings import ModelSettings

from src.plugins.zssm.config import Config
from src.providers.llm import UsageTracker, create_agent, resolve_endpoint
from src.providers.llm.media import as_model_inputs

config = get_plugin_config(Config)

VL_PROMPT = "请你作为你文本模型姐妹的眼睛, 告诉她这张图片的内容"


async def process_image(
    image: Image, tracker: UsageTracker | None = None
) -> str | None:
    """处理图片内容, 返回图片描述

    Args:
        image: 待识别的图片
        tracker: 用量统计器, 传入时记录本次调用的 token 消耗

    Returns:
        Optional[str]: 图片描述内容, 失败时返回 None
    """
    if not config.zssm_ai_vl_model:
        return None
    endpoint = resolve_endpoint(config.zssm_ai_vl_model)
    if endpoint is None:
        return None

    # 取图与转码交给 providers.llm.media：它先走适配器取图，再回落到直连下载，
    # 所以没有公网 URL 的图（OneBot 的 file id 一类）这里也能拿到
    contents = await as_model_inputs([image])
    if not contents:
        logger.warning("图片获取失败")
        return None

    agent = create_agent(endpoint, settings=ModelSettings(timeout=120))

    try:
        logger.info(f"开始处理图片: {config.zssm_ai_vl_model}")
        result = await agent.run([VL_PROMPT, *contents])
    except Exception as e:
        logger.opt(exception=e).error("图片处理失败")
        return None

    if tracker:
        tracker.record(endpoint.name, result)

    logger.info("图片处理完成")
    return result.output
