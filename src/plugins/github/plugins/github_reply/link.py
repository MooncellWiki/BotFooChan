from nonebot import on_command

from src.plugins.github import config
from src.plugins.github.cache.message_tag import (
    CommitTag,
    IssueTag,
    PullRequestTag,
    ReleaseTag,
    create_message_tag,
)
from src.plugins.github.dependencies import OPTIONAL_REPLY_TAG, REPLY_TAG
from src.plugins.github.helpers import NO_GITHUB_EVENT, PREFIXED_COMMAND
from src.providers.platform import (
    MESSAGE_INFO,
    TARGET_INFO,
    TargetType,
    extract_sent_message,
)

link = on_command(
    "link",
    aliases={"链接"},
    rule=PREFIXED_COMMAND & NO_GITHUB_EVENT,
    priority=config.github_command_priority,
    block=True,
)


@link.handle()
async def handle_no_reply(tag: OPTIONAL_REPLY_TAG):
    if tag is None:
        await link.finish("请回复 GitHub 相关消息来获取链接")


@link.handle()
async def handle_link(
    target_info: TARGET_INFO,
    message_info: MESSAGE_INFO,
    tag: REPLY_TAG,
):
    await create_message_tag(
        message_info,
        tag.model_copy(update={"is_receive": True}),
    )

    url = f"https://github.com/{tag.owner}/{tag.repo}"
    match tag:
        case IssueTag():
            url += f"/issues/{tag.number}"
        case PullRequestTag():
            url += f"/pull/{tag.number}"
        case CommitTag():
            url += f"/commit/{tag.commit}"
        case ReleaseTag():
            url += f"/releases/tag/{tag.tag}"

    match target_info.type:
        case TargetType.QQ_USER | TargetType.QQ_GROUP:
            result = await link.send(url)
        case (
            TargetType.QQ_OFFICIAL_USER
            | TargetType.QQGUILD_USER
            | TargetType.QQ_OFFICIAL_GROUP
            | TargetType.QQGUILD_CHANNEL
        ):
            result = await link.send(url)

    tag = tag.model_copy(update={"is_receive": False})
    if sent_message_info := extract_sent_message(target_info, result):
        await create_message_tag(sent_message_info, tag)
