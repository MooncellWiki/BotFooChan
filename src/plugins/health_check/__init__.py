# 搬自 QQ-GitHub-Bot。原版还要探 Postgres 和 Redis，这里数据库换成了 ORM 的默认库，
# Redis 已经去掉；浏览器是远程的 Playwright Server，get_browser() 断线时会顺手重连

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import nonebot
from nonebot import logger, require
from sqlalchemy import text

require("nonebot_plugin_orm")
from nonebot_plugin_orm import get_session

from src.providers.playwright import get_browser

app: FastAPI = nonebot.get_app()


@app.get("/health")
async def health_check():
    """Health check endpoint."""

    # check database connection
    try:
        async with get_session() as session:
            (await session.scalars(text("SELECT 1"))).all()
    except Exception as e:
        logger.opt(exception=e).error("Database connection health check failed.")
        return JSONResponse(
            {"status": "error", "component": "database"}, status_code=503
        )

    # check playwright connection
    try:
        if not (await get_browser()).is_connected():
            raise RuntimeError("Playwright browser is not connected.")
    except Exception as e:
        logger.opt(exception=e).error("Playwright connection health check failed.")
        return JSONResponse(
            {"status": "error", "component": "playwright"}, status_code=503
        )

    return JSONResponse({"status": "ok"}, status_code=200)
