"""导出 WebUI 接口的 OpenAPI 文档，前端据此生成客户端（web/app/client）::

    uv run python scripts/dump_webui_openapi.py > web/openapi.json
    cd web && pnpm gen

只初始化 NoneBot、加载 webui 插件，不注册适配器，也不连数据库。
"""

import io
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
# NoneBot 从当前目录读 .env，插件按 src.plugins.* 导入，都要以仓库根目录为准
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import nonebot
from nonebot.log import default_filter, default_format, logger


def main() -> None:
    # NoneBot 默认把日志打到 stdout，会混进导出的 JSON 里
    logger.remove()
    logger.add(sys.stderr, filter=default_filter, format=default_format)
    nonebot.init(log_level="WARNING")
    nonebot.load_plugin("src.plugins.webui")

    from src.plugins.webui.api import build_api

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stdout.write(
        json.dumps(build_api().openapi(), ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
