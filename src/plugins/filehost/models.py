from typing import Literal
from collections.abc import Mapping, Sequence

from starlette.datastructures import Headers
from pydantic import Extra, BaseModel, IPvAnyAddress


class RequestHeaders(Headers):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        if isinstance(value, Sequence) and all(isinstance(e, Sequence) for e in value):
            return cls(raw=value)  # type:ignore
        elif isinstance(value, Mapping):
            if all(isinstance(k, str) for k in value.keys()) and all(
                isinstance(v, str) for v in value.values()
            ):
                return cls(headers=value)
            else:
                return cls(scope=value)  # type:ignore
        raise ValueError("Invalid request headers.")


class RequestScopeInfo(BaseModel):
    """
    This is scope model for uvicorn

    Reference: https://www.uvicorn.org/#http-scope
    """

    class Config:
        extra = Extra.allow

    asgi: Mapping[str, str]

    type: Literal["http", "websocket"]
    server: tuple[IPvAnyAddress, int]
    client: tuple[IPvAnyAddress, int]

    scheme: str
    method: str | None = None
    http_version: str | None = None
    root_path: str
    path: str
    headers: RequestHeaders
