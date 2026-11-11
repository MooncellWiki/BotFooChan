from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

from src.plugins.webui.auth import Admin


class Ok(BaseModel):
    ok: bool = True


class Page[T](BaseModel):
    items: list[T]
    total: int


def aware(value: datetime) -> datetime:
    """SQLite 取回来的时间不带时区，按存进去时的 UTC 补上，免得前端当成本地时间"""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def actor(admin: Admin) -> str:
    """审计记录里的操作人"""
    return f"github:{admin.login}"


def not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what}不存在")


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def unavailable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, message)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def invalid(
    error: ValidationError, prefix: tuple[str | int, ...] = ()
) -> HTTPException:
    """pydantic 校验错误转成 FastAPI 的 422 格式，前端能按字段路径显示"""
    detail: list[dict[str, Any]] = [
        {"loc": ["body", *prefix, *e["loc"]], "msg": e["msg"], "type": e["type"]}
        for e in error.errors()
    ]
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail)
