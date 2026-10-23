from githubkit import GitHub
import nonebot
from nonebot.adapters.github import GitHubBot, OAuthBot

from . import config


def get_github_bot() -> GitHubBot:
    """Get the GitHub bot instance"""
    return nonebot.get_bot(config.github_app.app_id)  # type: ignore


def get_oauth_bot() -> OAuthBot:
    """Get the OAuth bot instance"""
    if not config.oauth_app:
        raise ValueError("No OAuth app configured")
    return nonebot.get_bot(config.oauth_app.client_id)  # type: ignore


def get_github() -> GitHub:
    """Get the github app client"""
    return get_github_bot().github


def get_oauth_github() -> GitHub:
    """Get the oauth app client"""
    return get_oauth_bot().github
