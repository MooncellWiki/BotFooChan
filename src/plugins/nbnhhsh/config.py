from pydantic import Field, HttpUrl, BaseModel


class Config(BaseModel):
    nbnhhsh_api_endpoint: HttpUrl = Field("https://lab.magiconch.com")
