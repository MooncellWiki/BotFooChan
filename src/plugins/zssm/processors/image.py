"""图片内容识别（视觉模型调用基于 pydantic-ai 统一封装）"""

from io import BytesIO
import ssl

import httpx
from nonebot import get_plugin_config, logger
from nonebot_plugin_alconna.uniseg import Image
from PIL import Image as PILImage
from pydantic_ai import BinaryContent
from pydantic_ai.settings import ModelSettings

from src.plugins.zssm.config import Config
from src.providers.llm import UsageTracker, create_agent, resolve_endpoint

config = get_plugin_config(Config)

VL_PROMPT = "请你作为你文本模型姐妹的眼睛, 告诉她这张图片的内容"


async def download_image_as_jpeg(url: str) -> bytes:
    """下载图片并转为 JPEG（超过 5MB 时缩小分辨率）"""
    ssl_context = ssl.create_default_context()
    ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_3
    ssl_context.set_ciphers("HIGH:!aNULL:!MD5")

    async with httpx.AsyncClient(verify=ssl_context) as client:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()

    image = PILImage.open(BytesIO(response.content))
    if len(response.content) > 5 * 1024 * 1024:
        image.thumbnail((4096, 4096))
    if image.mode != "RGB":
        image = image.convert("RGB")

    buffered = BytesIO()
    image.save(buffered, format="JPEG", quality=80)
    return buffered.getvalue()


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
    if not image.url or not config.zssm_ai_vl_model:
        return None
    endpoint = resolve_endpoint(config.zssm_ai_vl_model)
    if endpoint is None:
        return None

    agent = create_agent(endpoint, settings=ModelSettings(timeout=120))

    try:
        logger.info(f"开始处理图片: {config.zssm_ai_vl_model} - {image.url}")
        jpeg = await download_image_as_jpeg(image.url)
        result = await agent.run(
            [VL_PROMPT, BinaryContent(data=jpeg, media_type="image/jpeg")]
        )
    except Exception as e:
        logger.opt(exception=e).error("图片处理失败")
        return None

    if tracker:
        tracker.record(endpoint.name, result)

    logger.info("图片处理完成")
    return result.output
