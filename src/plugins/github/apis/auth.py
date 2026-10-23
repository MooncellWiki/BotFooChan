from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import nonebot
from nonebot import logger

from src.plugins.github.libs.auth import (
    consume_state,
    create_auth_user,
    get_token_by_code,
)

from . import env

app: FastAPI = nonebot.get_app()
template = env.get_template("auth.html.jinja")


@app.get("/github/auth", response_class=HTMLResponse)
async def auth(code: str, state: str | None = None):
    """OAuth callback endpoint"""

    if not state:
        return await template.render_async(title="Invalid OAuth Session!", icon="error")

    try:
        token = await get_token_by_code(code)
    except Exception as e:
        logger.opt(exception=e).error("Failed to get oauth token!")
        return await template.render_async(
            title="Oops...", text="Invalid oauth code!", icon="error"
        )

    if not token:
        return await template.render_async(
            title="Oops...", text="Invalid oauth code!", icon="error"
        )

    user_info = await consume_state(state)
    if not user_info:
        return await template.render_async(
            title="Oops...", text="OAuth Session Expired!", icon="error"
        )

    try:
        user = await create_auth_user(user_info, access_token=token)
    except Exception as e:
        logger.opt(exception=e).error(
            "Failed to update access_token for user!", user=user_info.model_dump()
        )
        return await template.render_async(
            title="Oops...", text="Failed to bind user!", icon="error"
        )

    return await template.render_async(
        title="Install Complete!",
        text=f"Successfully bind user {user.to_user_info().user_id}",
        icon="success",
    )
