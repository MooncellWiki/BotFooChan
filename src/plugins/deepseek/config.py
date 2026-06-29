from pydantic import BaseModel, Field


class DeepSeekConfig(BaseModel):
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    max_history: int = Field(default=20, ge=1, le=100)
    timeout: int = 100


class Config(BaseModel):
    deepseek: DeepSeekConfig = Field(default_factory=DeepSeekConfig)
