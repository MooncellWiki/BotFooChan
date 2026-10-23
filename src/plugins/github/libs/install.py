import urllib.parse

from src.plugins.github.cache import create_state
from src.plugins.github.utils import get_github_bot
from src.providers.platform import UserInfo


async def create_install_link(user: UserInfo) -> str:
    """Create github app installation link"""
    query = {"state": await create_state(user)}
    return (
        f"https://github.com/apps/{get_github_bot()._app_slug}/"
        f"installations/new?{urllib.parse.urlencode(query)}"
    )


async def config_install_link(installation_id: int) -> str:
    """Create github app installation config link"""
    return f"https://github.com/apps/{get_github_bot()._app_slug}/installations/{installation_id}"
