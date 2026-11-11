from pydantic import BaseModel, ConfigDict, Field


class CDNDomain(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    api_url: str = "https://cdn.aliyuncs.com"
    """CDN 接口地址"""
    access_key_secret: str = Field(json_schema_extra={"secret": True})
    access_key_id: str = Field(json_schema_extra={"secret": True})
    domains: list[str]
    """这个账号下要查询的域名"""
    group_alias: str
    """账号的显示名"""


class Config(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    cdn_domains: list[CDNDomain]
    """要查询的阿里云账号及其 CDN 域名"""
