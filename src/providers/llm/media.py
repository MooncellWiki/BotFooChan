"""把消息里的图片整理成模型能直接吃的多模态输入。

聊天平台给过来的图片形态不一：OneBot 只给一个 file id，官方机器人给短时效 URL，
格式上还可能是模型不认的 BMP/TIFF。这里统一成「取字节 → 规整 → BinaryContent」：

- 取字节优先走 uniseg 的 :func:`image_fetch`（各适配器的差异它都兜住了），
  失败再用 httpx 直连 URL 兜底（QQ 图床对 TLS 握手挑剔，需要放宽参数）
- 规整保证媒体类型落在 JPEG/PNG/GIF/WebP 内，并把过大的图等比缩小：模型侧本来
  就会缩到约 1300×1300 等效像素（每张图最多 1024 token），再大只是白占请求体

限制与计费规则见 https://api-docs.deepseek.com/zh-cn/guides/vision
"""

import asyncio
from collections.abc import Sequence
from io import BytesIO
import ssl

import httpx
from nonebot import logger
from nonebot.matcher import current_bot, current_event
from nonebot.utils import run_sync
from nonebot_plugin_alconna.uniseg import Image, image_fetch
from PIL import Image as PILImage
from pydantic_ai import BinaryContent

MEDIA_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}
"""模型认得的图片格式 -> 媒体类型，其余格式一律转码成 JPEG"""

MAX_EDGE = 2048
"""长边超过该像素数就等比缩小"""
MAX_BYTES = 2 * 1024 * 1024
"""单张图片超过该体积就转码成 JPEG。

多轮对话每轮都要把历史里的图片整个重发一遍，而模型那边反正会缩到约 1300×1300
等效像素，留着几 MB 的原图纯属浪费（单次请求体上限 48 MiB）。
"""
DOWNLOAD_TIMEOUT = 30.0


def _tls_context() -> ssl.SSLContext:
    """QQ 图床的证书链在默认握手参数下常谈不拢，放宽协议与加密套件"""
    context = ssl.create_default_context()
    context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_3
    context.set_ciphers("HIGH:!aNULL:!MD5")
    return context


async def download_image(url: str) -> bytes:
    """直连下载一张图片"""
    async with httpx.AsyncClient(
        verify=_tls_context(), follow_redirects=True
    ) as client:
        response = await client.get(url, timeout=DOWNLOAD_TIMEOUT)
        response.raise_for_status()
    return response.content


def normalize_image(data: bytes) -> BinaryContent | None:
    """按模型的格式与尺寸要求规整图片，认不出格式时返回 None"""
    try:
        with PILImage.open(BytesIO(data)) as image:
            media_type = MEDIA_TYPES.get(image.format or "")
            if media_type and max(image.size) <= MAX_EDGE and len(data) <= MAX_BYTES:
                return BinaryContent(data=data, media_type=media_type)

            # 动图只取首帧：多帧对理解没帮助，转码反而容易吃满内存
            rgba = image.convert("RGBA")
            frame = PILImage.new("RGB", rgba.size, "white")
            frame.paste(rgba, mask=rgba.getchannel("A"))
            frame.thumbnail((MAX_EDGE, MAX_EDGE))

            buffer = BytesIO()
            frame.save(buffer, format="JPEG", quality=85)
    except Exception as e:
        logger.opt(exception=e).warning("图片解析失败，已跳过")
        return None

    return BinaryContent(data=buffer.getvalue(), media_type="image/jpeg")


async def fetch_image(image: Image) -> bytes | None:
    """取出一张图片的原始字节，取不到时返回 None"""
    if image.raw:
        return image.raw_bytes
    try:
        if data := await image_fetch(current_event.get(), current_bot.get(), {}, image):
            return data
    except Exception as e:
        logger.opt(exception=e).debug("适配器取图失败，改为直连下载")

    if not image.url:
        return None
    try:
        return await download_image(image.url)
    except Exception as e:
        logger.opt(exception=e).warning(f"图片下载失败：{image.url}")
        return None


async def as_model_inputs(
    images: Sequence[Image], *, limit: int | None = None
) -> list[BinaryContent]:
    """消息里的图片 -> 模型输入；取不到或认不出的图片直接丢掉

    单张图失败不该拖垮整次提问，因此这里只记日志，由调用方按数量差异决定是否提示。
    """
    selected = images if limit is None else images[:limit]
    payloads = await asyncio.gather(*(fetch_image(image) for image in selected))
    # 缩放与转码是纯 CPU 活，扔线程里别卡住事件循环
    contents = await asyncio.gather(
        *(run_sync(normalize_image)(data) for data in payloads if data)
    )
    return [content for content in contents if content is not None]
