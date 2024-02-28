from pydantic import BaseModel


class ShareClickResponseData(BaseModel):
    title: str
    picture: str
    link: str
    program_id: str
    share_mode: int
    program_path: str
    header: str
    count: int


class ShareClickResponse(BaseModel):
    code: int
    message: str
    ttl: int
    data: ShareClickResponseData
