from pydantic import BaseModel


class CDNDomain(BaseModel):
    api_url: str = "https://cdn.aliyuncs.com"
    access_key_secret: str
    access_key_id: str
    domains: list[str]
    group_alias: str


class Config(BaseModel):
    cdn_domains: list[CDNDomain]
