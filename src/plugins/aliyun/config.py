from pydantic import Extra, Field, HttpUrl, BaseModel


class CDNDomain(BaseModel, extra=Extra.ignore):
    api_url: HttpUrl = Field("https://cdn.aliyuncs.com")
    access_key_secret: str
    access_key_id: str
    domains: list[str]
    group_alias: str


class Config(BaseModel, extra=Extra.ignore):
    cdn_domains: list[CDNDomain]
