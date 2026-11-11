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

## WebUI

管理后台和机器人跑在同一个进程、同一个端口：页面在 `/admin/`，接口在 `/admin/api`（`src/plugins/webui`）。前端在 `web/`（Nuxt 4 + Nuxt UI），镜像构建时生成静态文件一起打进去。

启用：

1. `.env.prod` 里配 `WEBUI__SECRET_KEY`、`WEBUI__PUBLIC_URL`、`WEBUI__ADMINS`，说明见 `.env`
2. 在 GitHub App 的设置里把 `<WEBUI__PUBLIC_URL>/admin/api/auth/callback` 加进 Callback URL
3. 反向代理把 `/admin` 转给 bot，要走 HTTPS（cookie 带 `Secure`）

本地开发（Node 26 + pnpm）：

```sh
# 后端照常起 bot；.env.dev 里配 WEBUI__DEV_ADMIN=<GitHub 用户名> 可以免登录
uv run python bot.py
# 前端：打开 http://localhost:3000/admin/，接口转给 127.0.0.1:8086（换端口用 WEBUI_DEV_API）
cd web && pnpm install && pnpm dev
```

改了接口之后重新生成前端的客户端，CI 会检查两边是否一致：

```sh
uv run python scripts/dump_webui_openapi.py > web/openapi.json && (cd web && pnpm gen)
```
