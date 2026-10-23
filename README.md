# BotFooChan

[![LICENSE](https://img.shields.io/github/license/MooncellWiki/BotFooChan)](https://github.com/MooncellWiki/BotFooChan/blob/main/LICENSE)
![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg?logo=python&logoColor=edb641)
[![NoneBot Version](https://img.shields.io/badge/nonebot-2+-red.svg)](https://nonebot.dev/)
![Black](https://img.shields.io/badge/code%20style-black-000000.svg?logo=python&logoColor=edb641)
![Pyright](https://img.shields.io/badge/types-pyright-797952.svg?logo=python&logoColor=edb641)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)

[![Release](https://github.com/MooncellWiki/BotFooChan/actions/workflows/release.yml/badge.svg?branch=main)](https://hub.docker.com/r/MooncellWiki/BotFooChan)
[![Pre-Commit](https://results.pre-commit.ci/badge/github/MooncellWiki/BotFooChan/main.svg)](https://results.pre-commit.ci/latest/github/MooncellWiki/BotFooChan/main)
[![Pyright](https://github.com/MooncellWiki/BotFooChan/actions/workflows/pyright.yml/badge.svg?branch=main&event=push)](https://github.com/MooncellWiki/BotFooChan/actions/workflows/pyright.yml)
[![Ruff](https://github.com/MooncellWiki/BotFooChan/actions/workflows/ruff.yml/badge.svg?branch=main&event=push)](https://github.com/MooncellWiki/BotFooChan/actions/workflows/ruff.yml)

供 Mooncell 协作使用的跨平台机器人

## 简介

在 QQ 等平台查询阿里云业务状态，查询 FGO/明日方舟 相关动态及推送

## GitHub 功能

合并自 yanyongyu [QQ-GitHub-Bot](https://github.com/cscs181/QQ-GitHub-Bot)：查看 Issue/PR 时间线截图、订阅仓库事件推送、回复推送消息进行评论/合并/打标签等操作、`/status` 查看运行状态。命令与原版一致，但都需要带 `/` 前缀。

与原版的差别：

- 数据库用 ORM 默认的 SQLite，不再需要 Postgres；原 Redis 里的缓存改存在 `LOCALSTORE_CACHE_DIR` 下（`src/providers/cache`）
- 截图走项目自己的 Playwright（远程 Firefox），不再在 bot 容器里装浏览器
- 没有配置 `GITHUB_APPS` 时 GitHub 插件只打警告、不加载，不影响其它功能

从原版迁移数据见 `scripts/import_qq_github_bot.py` 的说明。
