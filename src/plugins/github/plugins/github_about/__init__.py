# 原版是顶层插件 about。它离不开 GitHub 插件的 OpenGraph 和消息标记，挪成子插件后
# 就随 GitHub 插件一起启用：没配 GitHub App 时不会因为导入失败而报错

from nonebot import on_command
from nonebot.adapters import Bot
from nonebot.adapters.qq import MessageSegment as QQOfficialMS
from nonebot.plugin import PluginMetadata

from src.plugins.github.cache.message_tag import RepoTag, create_message_tag
from src.plugins.github.helpers import NO_GITHUB_EVENT, PREFIXED_COMMAND
from src.plugins.github.libs.opengraph import get_opengraph_image
from src.providers.platform import (
    MESSAGE_INFO,
    TARGET_INFO,
    TargetType,
    extract_sent_message,
)
from src.providers.platform.qq_client import image_segment

__plugin_meta__ = PluginMetadata(
    "关于",
    "获取关于本机器人的信息",
    "使用 /about 命令获取关于本机器人的信息",
)

OWNER = "cscs181"
REPO = "QQ-GitHub-Bot"
HOMEPAGE = f"https://github.com/{OWNER}/{REPO}"


about = on_command(
    "about",
    aliases={"关于"},
    rule=PREFIXED_COMMAND & NO_GITHUB_EVENT,
    priority=10,
    block=True,
)


@about.handle()
async def handle_about(
    event_bot: Bot, target_info: TARGET_INFO, message_info: MESSAGE_INFO
):
    await create_message_tag(
        message_info, RepoTag(owner=OWNER, repo=REPO, is_receive=True)
    )

    tag = RepoTag(owner=OWNER, repo=REPO, is_receive=False)

    if not (image := await get_opengraph_image(tag)):
        result = await about.send(HOMEPAGE)
    else:
        match target_info.type:
            case TargetType.QQ_USER | TargetType.QQ_GROUP:
                result = await about.send(image_segment(event_bot, image))
            case (
                TargetType.QQ_OFFICIAL_USER
                | TargetType.QQGUILD_USER
                | TargetType.QQ_OFFICIAL_GROUP
                | TargetType.QQGUILD_CHANNEL
            ):
                result = await about.send(QQOfficialMS.file_image(image))

    if sent_message_info := extract_sent_message(target_info, result):
        await create_message_tag(sent_message_info, tag)


from . import apis as apis
