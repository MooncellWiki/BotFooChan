from typing import Annotated, TypeAlias

from pydantic import Field

from ._base import BaseTargetInfo as BaseTargetInfo
from ._base import TargetType as TargetType

# isort: split

from .user import BaseUserInfo as BaseUserInfo
from .user import QQGuildUserInfo as QQGuildUserInfo
from .user import QQOfficialUserInfo as QQOfficialUserInfo
from .user import QQUserInfo as QQUserInfo
from .user import UserInfo as UserInfo

# isort: split

from .group import BaseGroupInfo as BaseGroupInfo
from .group import GroupInfo as GroupInfo
from .group import QQGroupInfo as QQGroupInfo
from .group import QQGuildChannelInfo as QQGuildChannelInfo
from .group import QQOfficialGroupInfo as QQOfficialGroupInfo

TargetInfo: TypeAlias = Annotated[UserInfo | GroupInfo, Field(discriminator="type")]
