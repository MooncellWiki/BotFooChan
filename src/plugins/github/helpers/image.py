from nonebot import require
from nonebot.adapters.qq import MessageSegment as QQOfficialMS

require("nonebot_plugin_filehost")
from nonebot_plugin_filehost import FileHost

QQOFFICIAL_IMAGE_MAX_SIZE = 2 * 1024 * 1024


async def qqofficial_conditional_image(image: bytes) -> QQOfficialMS:
    """Get the QQ official image message segment depends on image size"""
    if len(image) > QQOFFICIAL_IMAGE_MAX_SIZE:
        # 原版存进 Redis 再由自带的路由吐出来，这里改用项目里已有的 filehost 插件
        return QQOfficialMS.image(await FileHost(image, suffix=".png").to_url())
    return QQOfficialMS.file_image(image)
