from pydantic import BaseModel


class Ok(BaseModel):
    ok: bool = True
