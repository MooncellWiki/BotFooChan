# 搬自 QQ-GitHub-Bot（见 README）。和原版的差别主要在基础设施：数据库
# 从 Postgres 换成 ORM 默认的 SQLite，Redis 换成 src/providers/cache，浏览器用项目
# 自己的 Playwright provider；另外 GitHub 命令都要求带 / 前缀，见 helpers/rule.py

from pathlib import Path

import nonebot
from nonebot import get_plugin_config, logger, require
from nonebot.plugin import PluginMetadata
from pydantic import ValidationError

require("nonebot_plugin_orm")

# 模型不管有没有配置 GitHub App 都要加载：ORM 的启动检查只认得已加载模型的插件的
# 迁移，库里记着 github 的迁移版本、这边却找不到对应脚本时，整个 bot 都起不来
from . import models as models
from .config import Config

__plugin_meta__ = PluginMetadata(
    "GitHub",
    "在聊天里查看、订阅和操作 GitHub 仓库、Issue 与 PR",
    "见子插件使用方法",
)

try:
    # load all github plugin config from global config
    config = get_plugin_config(Config)
except ValidationError as e:
    # 不把 e 整个打出来：pydantic 的报错会带上输入值，也就是 App 的私钥
    logger.warning(
        "未配置可用的 GitHub App（GITHUB_APPS），GitHub 相关功能不会加载："
        + "；".join(error["msg"] for error in e.errors())
    )
else:
    # load all github subplugins
    _sub_plugins = set()
    _sub_plugins |= nonebot.load_plugins(
        str((Path(__file__).parent / "plugins").resolve())
    )

    # load all webhook subplugins
    _webhook_plugins = set()
    _webhook_plugins |= nonebot.load_plugins(
        str((Path(__file__).parent / "webhooks").resolve())
    )

    from . import apis as apis
