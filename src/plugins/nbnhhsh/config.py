from pydantic import BaseModel, ConfigDict


class Config(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    nbnhhsh_api_endpoint: str = "https://lab.magiconch.com"
    """缩写查询接口"""
    nbnhhsh_split_char: str = "，"
    """多个释义之间的分隔符"""
