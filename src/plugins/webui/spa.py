"""托管 Nuxt 生成的静态前端（``pnpm generate`` 的产物）"""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from nonebot import logger

from .config import BASE_PATH

ASSETS_DIR = "_nuxt"
"""带内容哈希的构建产物，可以长期缓存"""


def mount_spa(app: FastAPI, dist: Path) -> None:
    """在 BASE_PATH 下提供前端页面。

    要在接口挂载之后调用：这里注册的是兜底的 GET 路由，先注册的接口优先匹配。
    """
    root = dist.resolve()
    index = root / "index.html"
    if not index.is_file():
        logger.warning(f"没找到 WebUI 的前端构建产物（{root}），先只提供接口")

    @app.get(BASE_PATH, include_in_schema=False)
    async def webui_root() -> RedirectResponse:
        return RedirectResponse(f"{BASE_PATH}/")

    @app.get(BASE_PATH + "/{path:path}", include_in_schema=False)
    async def webui_page(path: str) -> Response:
        head = path.split("/", 1)[0]
        # 走到这里的 api 路径都是接口里不存在的，不要拿页面去顶
        if head == "api":
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        if not index.is_file():
            return PlainTextResponse(
                "WebUI 的前端还没构建：cd web && pnpm install && pnpm generate",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if path:
            file = (root / path).resolve()
            if file.is_relative_to(root) and file.is_file():
                cache = (
                    "public, max-age=31536000, immutable"
                    if head == ASSETS_DIR
                    else "no-cache"
                )
                return FileResponse(file, headers={"Cache-Control": cache})
            # 发版后旧页面还在请求上一版的产物，回个页面只会让它解析报错
            if head == ASSETS_DIR:
                raise HTTPException(status.HTTP_404_NOT_FOUND)
        # 其余路径都是前端路由，交给前端
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
