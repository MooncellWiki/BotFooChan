from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict, Field

from src.libs.llm import ApiType, ModelEndpoint


class ScopedConfig(BaseModel):
    api_key: str = ""
    """LLM API Key（缺省时回退使用 DEEPSEEK__API_KEY）"""
    base_url: str = "https://api.deepseek.com"
    """OpenAI 兼容 API 地址"""
    model: str = "deepseek-v4-flash"
    """模型名称"""
    api_type: ApiType | None = None
    """调用协议；缺省时 DeepSeek 官方走 Responses API，其余走 chat completions"""
    proxy: str | None = None
    """代理地址"""
    timeout: int = 60
    """API 请求超时（秒）"""
    temperature: float = Field(default=1.2, ge=0, le=2)
    """采样温度；调高可以让推荐更多样"""


class _DeepSeekConfig(BaseModel):
    """仅用于回退读取 deepseek 插件的 API Key"""

    model_config = ConfigDict(extra="ignore")

    api_key: str = ""


class Config(BaseModel):
    what2eat: ScopedConfig = Field(default_factory=ScopedConfig)
    """What2Eat Plugin Config"""
    deepseek: _DeepSeekConfig = Field(default_factory=_DeepSeekConfig)


_config = get_plugin_config(Config)
w2e_config = _config.what2eat

_api_key = w2e_config.api_key or _config.deepseek.api_key


def get_endpoint() -> ModelEndpoint | None:
    """获取推荐所用的模型端点，未配置 API Key 时返回 None"""
    if not _api_key:
        return None
    return ModelEndpoint(
        name=w2e_config.model,
        base_url=w2e_config.base_url,
        api_key=_api_key,
        api_type=w2e_config.api_type,
        proxy=w2e_config.proxy,
    )
