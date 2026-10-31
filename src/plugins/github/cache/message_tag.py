# 子类收窄父类字段的类型是有意为之（pydantic 判别字段、已授权/已绑定的模型），
# 原版在全局关了这条检查
# pyright: reportIncompatibleVariableOverride=false

from datetime import timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from src.providers import cache
from src.providers.platform import MessageInfo

MESSAGE_TAG_CACHE_KEY = "github:message:{type}:{message_id}:tag"
MESSAGE_TAG_CACHE_EXPIRE = timedelta(days=1)


class RepoTag(BaseModel):
    """Repo tag"""

    type: Literal["repo"] = "repo"
    owner: str
    repo: str
    is_receive: bool


class IssueTag(RepoTag):
    """Issue tag"""

    type: Literal["issue"] = "issue"
    number: int


class PullRequestTag(RepoTag):
    """Pull request tag"""

    type: Literal["pull_request"] = "pull_request"
    number: int


class CommitTag(RepoTag):
    """Commit tag"""

    type: Literal["commit"] = "commit"
    commit: str


class ReleaseTag(RepoTag):
    """Release tag"""

    type: Literal["release"] = "release"
    tag: str


Tag = Annotated[
    RepoTag | IssueTag | PullRequestTag | CommitTag | ReleaseTag,
    Field(discriminator="type"),
]
"""Tag types"""


async def create_message_tag(message: MessageInfo, tag: Tag) -> None:
    """Create message tag cache

    Args:
        message: Message info
        tag: Tag data
    """

    await cache.set(
        MESSAGE_TAG_CACHE_KEY.format(type=message.type.value, message_id=message.key),
        tag.model_dump_json(),
        ex=MESSAGE_TAG_CACHE_EXPIRE,
    )


async def get_message_tag(message: MessageInfo) -> Tag | None:
    """Get message tag cache

    Args:
        platform: Platform name
        message_id: Message id

    Returns:
        Existing tag data
    """
    data: bytes | None
    if (
        data := await cache.get(
            MESSAGE_TAG_CACHE_KEY.format(
                type=message.type.value, message_id=message.key
            )
        )
    ) is not None:
        return TypeAdapter(Tag).validate_json(data)
