from nonebot.adapters import Event
from nonebot.params import CommandStart
from nonebot.rule import Rule

from src.plugins.github.cache.message_tag import IssueTag, PullRequestTag
from src.plugins.github.dependencies import OPTIONAL_REPLY_TAG
from src.providers.platform import (
    OPTIONAL_GROUP_INFO,
    OPTIONAL_IS_PRIVATE,
    is_supported_event,
)


async def no_github_event(event: Event):
    """Check if the event is not a github webhook event"""
    # 原版只排除 GitHub webhook 事件。这里还接着飞书这类 platform provider 认不出的
    # 平台，它们的消息放进来只会在依赖里报一句 Unprocessed event type 再静默结束，
    # 所以改成只放行认得出来的聊天事件（GitHub 事件自然也在其外）
    return is_supported_event(event)


NO_GITHUB_EVENT = Rule(no_github_event)


async def prefixed_command(command_start: str = CommandStart()) -> bool:
    """Check if the command is sent with a non-empty command start"""
    # 本项目的 COMMAND_START 含空串，不加这条的话「搜索一下」「合并」「关于」这类
    # 日常用语都会被当成 GitHub 命令；QQ-GitHub-Bot 原本就只认 / 开头的命令
    return bool(command_start)


PREFIXED_COMMAND = Rule(prefixed_command)


async def match_when_private(is_private: OPTIONAL_IS_PRIVATE) -> bool:
    return is_private is True


MATCH_WHEN_PRIVATE = Rule(match_when_private)


async def match_when_group(group_info: OPTIONAL_GROUP_INFO) -> bool:
    return group_info is not None


MATCH_WHEN_GROUP = Rule(match_when_group)


async def match_when_private_or_group(
    is_private: OPTIONAL_IS_PRIVATE, group_info: OPTIONAL_GROUP_INFO
) -> bool:
    return is_private is True or group_info is not None


MATCH_WHEN_PRIVATE_OR_GROUP = Rule(match_when_private_or_group)


async def reply_any(reply_tag: OPTIONAL_REPLY_TAG) -> bool:
    return reply_tag is not None


REPLY_ANY = Rule(reply_any)


async def reply_issue_or_pr(reply_tag: OPTIONAL_REPLY_TAG) -> bool:
    return isinstance(reply_tag, IssueTag | PullRequestTag)


REPLY_ISSUE_OR_PR = Rule(reply_issue_or_pr)


async def reply_pr(reply_tag: OPTIONAL_REPLY_TAG) -> bool:
    return isinstance(reply_tag, PullRequestTag)


REPLY_PR = Rule(reply_pr)
