from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import nonebot

from . import HOMEPAGE

app: FastAPI = nonebot.get_app()


@app.get("/")
async def redirect_to_homepage() -> RedirectResponse:
    return RedirectResponse(HOMEPAGE)
