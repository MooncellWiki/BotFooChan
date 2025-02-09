from pydantic import BaseModel, ConfigDict


class Config(BaseModel):
    llm_api_key: str
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "deepseek/deepseek-r1:free"

    model_config = ConfigDict(extra="allow")
