from pydantic import BaseModel


class Config(BaseModel):
    nbnhhsh_api_endpoint: str = "https://lab.magiconch.com"
    nbnhhsh_split_char: str = "，"
