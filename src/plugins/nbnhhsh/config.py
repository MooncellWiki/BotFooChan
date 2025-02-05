from pydantic import BaseModel, Field, HttpUrl


class Config(BaseModel):
    nbnhhsh_api_endpoint: HttpUrl = Field("https://lab.magiconch.com")
    nbnhhsh_split_char: str = "，"
