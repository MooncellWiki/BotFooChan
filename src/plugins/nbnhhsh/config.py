from pydantic import Extra, Field, HttpUrl, BaseModel


class Config(BaseModel, extra=Extra.ignore):
    nbnhhsh_api_endpoint: HttpUrl = Field("https://lab.magiconch.com")
