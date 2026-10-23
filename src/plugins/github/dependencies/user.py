# 子类收窄父类字段的类型是有意为之（pydantic 判别字段、已授权/已绑定的模型），
# 原版在全局关了这条检查
# pyright: reportIncompatibleVariableOverride=false

from typing import TYPE_CHECKING, Annotated, TypeAlias

from githubkit.versions.latest.models import PrivateUser, PublicUser
from nonebot import logger
from nonebot.adapters.github import ActionFailed, ActionTimeout
from nonebot.matcher import Matcher
from nonebot.params import Depends

from src.plugins.github.models import User
from src.plugins.github.utils import get_github_bot
from src.providers.platform import USER_INFO


async def get_current_user(user: USER_INFO) -> User | None:
    """Get current database user from event."""
    return await User.from_info(user)


USER: TypeAlias = Annotated[User | None, Depends(get_current_user)]
"""Current database user from event. None if never authenticated."""

if TYPE_CHECKING:

    class AuthorizedUser(User):
        """Authorized user model"""

        access_token: str

else:
    AuthorizedUser = User


async def get_authorized_user(matcher: Matcher, user: USER) -> AuthorizedUser:
    """Get current database user from event.

    Finish the session if user is not authenticated.
    """
    if not user or not user.access_token:
        await matcher.finish("你还没有绑定 GitHub 帐号，请私聊使用 /install 进行安装")
    return user  # type: ignore


AUTHORIZED_USER: TypeAlias = Annotated[AuthorizedUser, Depends(get_authorized_user)]
"""Current database user from event. Finish the session if not authenticated."""


async def get_github_user(
    matcher: Matcher, user: AUTHORIZED_USER
) -> PrivateUser | PublicUser:
    """Get current GitHub user from event.

    Finish the session if user is not authenticated or API error occurs.
    """
    bot = get_github_bot()

    try:
        async with bot.as_user(user.access_token):
            resp = await bot.rest.users.async_get_authenticated()
            return resp.parsed_data
    except ActionTimeout:
        await matcher.finish("GitHub API 超时，请稍后再试")
    except ActionFailed as e:
        if e.response.status_code == 401:
            await matcher.finish("你的 GitHub 帐号授权已过期，请使用 /auth 进行刷新")
        logger.opt(exception=e).error(f"Failed while getting github user: {e}")
        await matcher.finish("未知错误发生，请尝试重试或联系管理员")
    except Exception as e:
        logger.opt(exception=e).error(f"Failed while getting github user: {e}")
        await matcher.finish("未知错误发生，请尝试重试或联系管理员")


GITHUB_USER: TypeAlias = Annotated[PrivateUser | PublicUser, Depends(get_github_user)]
"""Current GitHub user from event. Finish the session if not authenticated."""
