from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute

from src.plugins.webui.auth import check_csrf, require_admin
from src.plugins.webui.config import API_PATH, is_dev

from . import admin_api, auth, llm_api, overview, settings_api

PROTECTED_ROUTERS = (
    overview.router,
    settings_api.router,
    llm_api.router,
    admin_api.router,
)
"""要登录才能用的接口"""


def _operation_id(route: APIRoute) -> str:
    # 前端生成的客户端按它起函数名（getOverview、getMe……），所以直接用接口函数名
    return route.name


def build_api() -> FastAPI:
    """WebUI 的接口，作为子应用挂在 API_PATH 下"""
    dev = is_dev()
    api = FastAPI(
        title="BotFooChan WebUI",
        version="1",
        servers=[{"url": API_PATH}],
        generate_unique_id_function=_operation_id,
        dependencies=[Depends(check_csrf)],
        # 接口文档只在开发时开放
        docs_url="/docs" if dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if dev else None,
    )
    api.include_router(auth.router)
    for router in PROTECTED_ROUTERS:
        api.include_router(router, dependencies=[Depends(require_admin)])

    names = [route.name for route in api.routes if isinstance(route, APIRoute)]
    if duplicates := {name for name in names if names.count(name) > 1}:
        raise RuntimeError(f"WebUI 接口函数重名：{duplicates}")
    return api
