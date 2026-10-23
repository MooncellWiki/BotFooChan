import asyncio

from nonebot import logger, on_type
from nonebot.adapters.github import ReleasePublished
from nonebot.plugin import PluginMetadata

from src.plugins.github import config
from src.plugins.github.cache.message_tag import ReleaseTag
from src.plugins.github.libs.opengraph import get_opengraph_image

from ._dependencies import (
    SEND_INTERVAL,
    SUBSCRIBERS,
    send_subscriber_image,
    send_subscriber_text,
)

__plugin_meta__ = PluginMetadata(
    "GitHub Release 发布事件通知",
    "订阅 GitHub release/published 事件来接收通知",
    "通知以图片形式发送",
)

release = on_type(ReleasePublished, priority=config.github_webhook_priority, block=True)


@release.handle()
async def handle_release_published_event(
    event: ReleasePublished, subscribers: SUBSCRIBERS
):
    if not subscribers:
        return

    owner = event.payload.repository.owner.login
    repo = event.payload.repository.name

    tag = ReleaseTag(
        owner=owner, repo=repo, tag=event.payload.release.tag_name, is_receive=False
    )

    image = await get_opengraph_image(tag)

    fallback_msg = f"Release [{tag.tag}] published in {owner}/{repo}"

    for target in subscribers:
        try:
            if image:
                await send_subscriber_image(target.to_subscriber_info(), image, tag)
            else:
                await send_subscriber_text(
                    target.to_subscriber_info(), fallback_msg, tag
                )
        except Exception as e:
            logger.opt(exception=e).warning(
                "Send message to subscriber failed: {e}",
                target_info=target.to_subscriber_info(),
                e=e,
            )

        await asyncio.sleep(SEND_INTERVAL)
