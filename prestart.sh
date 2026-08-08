#! /usr/bin/env sh
# 由 docker/start.sh 在拉起 gunicorn 前 source（PRE_START_PATH 默认就是 /app/prestart.sh）。
#
# ALEMBIC_STARTUP_CHECK=true 时，数据库没升到最新迁移，bot 启动会直接失败：
# 那条检查在非交互终端下没法确认「是否更新」，只会抛错。所以这里先把迁移跑掉。
#
# 镜像里没有 nb-cli（Dockerfile 用 --no-dev 导出依赖），因此不能用 `nb orm upgrade`，
# 直接调 nonebot-plugin-orm 的 CLI；bot.py 负责 nonebot.init() 和加载插件，
# 迁移脚本的版本目录要靠插件加载完才能定位。
set -e

echo "Running database migrations"
python -c "
import bot  # noqa: F401  —— nonebot.init() + 注册适配器 + 加载插件

from nonebot_plugin_orm.__main__ import main

main(['upgrade'], prog_name='orm')
"
