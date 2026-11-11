"""管理后台：接口在 ``/admin/api``，前端页面在 ``/admin/``。

前端在仓库的 ``web/`` 下（Nuxt），镜像构建时生成静态文件，由这里一起托管；
登录走 GitHub OAuth，见 :mod:`.api.auth`。
"""

from pathlib import Path

from fastapi import FastAPI
import nonebot
from nonebot import logger, require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_orm")
require("nonebot_plugin_status")

from .api import build_api
from .auth import SECRET
from .config import (
    API_PATH,
    BASE_PATH,
    Config,
    dev_admin,
    oauth_credentials,
    webui_config,
)
from .spa import mount_spa

__plugin_meta__ = PluginMetadata(
    "WebUI",
    "机器人的管理后台",
    f"浏览器打开 {BASE_PATH}/，用 GitHub 账号登录",
    config=Config,
)


def _disabled_reason() -> str | None:
    if SECRET is None:
        return "没配 WEBUI__SECRET_KEY"
    if oauth_credentials() is None and dev_admin() is None:
        return (
            "没有 GitHub OAuth 凭据（WEBUI__GITHUB_CLIENT_ID / "
            "WEBUI__GITHUB_CLIENT_SECRET，"
            "或 GITHUB_APPS 里的 client_id / client_secret）"
        )
    return None


if reason := _disabled_reason():
    logger.warning(f"WebUI 没有启用：{reason}")
else:
    if not webui_config.admins and dev_admin() is None:
        logger.warning("WEBUI__ADMINS 是空的：后台里也没加过管理员的话，谁也登录不了")
    app: FastAPI = nonebot.get_app()
    app.mount(API_PATH, build_api())
    mount_spa(app, Path(webui_config.dist))
    logger.info(f"WebUI 挂载在 {BASE_PATH}/")
