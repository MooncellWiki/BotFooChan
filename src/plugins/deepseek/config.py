import json

from nonebot import get_plugin_config, logger
import nonebot_plugin_localstore as store
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.settings import ModelSettings

from src.libs.llm import ApiType, ModelEndpoint


class CustomModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    """模型名称"""
    alias: str | None = None
    """模型别名（用于展示与指定）"""
    base_url: str = "https://api.deepseek.com"
    """模型服务地址"""
    api_key: str | None = None
    """模型独立的 API Key（缺省时使用全局配置）"""
    api_type: ApiType | None = None
    """调用协议；缺省时 DeepSeek 官方走 Responses API，其余走 chat completions"""
    prompt: str | None = None
    """模型独立的人设（缺省时使用全局配置）"""
    proxy: str | None = None
    """代理地址"""
    max_tokens: int | None = Field(default=None, gt=1)
    """单次请求生成的最大 token 数"""
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    stop: str | list[str] | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)

    @property
    def display_name(self) -> str:
        return self.alias or self.name

    def to_endpoint(self, fallback_api_key: str | None = None) -> ModelEndpoint:
        return ModelEndpoint(
            name=self.name,
            base_url=self.base_url,
            api_key=self.api_key or fallback_api_key,
            api_type=self.api_type,
            proxy=self.proxy,
        )

    def to_settings(self, timeout: float) -> ModelSettings:
        settings = ModelSettings(timeout=timeout)
        if self.max_tokens is not None:
            settings["max_tokens"] = self.max_tokens
        if self.frequency_penalty is not None:
            settings["frequency_penalty"] = self.frequency_penalty
        if self.presence_penalty is not None:
            settings["presence_penalty"] = self.presence_penalty
        if self.stop is not None:
            settings["stop_sequences"] = (
                [self.stop] if isinstance(self.stop, str) else self.stop
            )
        if self.temperature is not None:
            settings["temperature"] = self.temperature
        if self.top_p is not None:
            settings["top_p"] = self.top_p
        return settings


class TimeoutConfig(BaseModel):
    api_request: int = Field(default=100)
    """API 请求超时（秒）"""
    user_input: int = Field(default=60)
    """多轮对话等待用户输入超时（秒）"""


class ScopedConfig(BaseModel):
    api_key: str = ""
    """DeepSeek API Key"""
    enable_models: list[CustomModel] = Field(
        default_factory=lambda: [
            CustomModel(name="deepseek-v4-flash"),
            CustomModel(name="deepseek-v4-pro"),
        ]
    )
    """启用的模型列表"""
    prompt: str = ""
    """全局人设"""
    md_to_pic: bool = False
    """Markdown 渲染为图片"""
    enable_send_thinking: bool = False
    """是否发送思维链"""
    timeout: int | TimeoutConfig = Field(default_factory=TimeoutConfig)
    """超时配置"""

    @property
    def api_timeout(self) -> int:
        return (
            self.timeout if isinstance(self.timeout, int) else self.timeout.api_request
        )

    @property
    def input_timeout(self) -> int:
        return (
            self.timeout if isinstance(self.timeout, int) else self.timeout.user_input
        )

    def get_enable_models(self) -> list[str]:
        return [model.display_name for model in self.enable_models]

    def get_model_config(self, model_name: str) -> CustomModel:
        for model in self.enable_models:
            if model_name in (model.name, model.alias):
                return model
        raise ValueError(f"Model {model_name} not enabled")


class Config(BaseModel):
    deepseek: ScopedConfig = Field(default_factory=ScopedConfig)
    """DeepSeek Plugin Config"""


ds_config = get_plugin_config(Config).deepseek


class ModelConfig:
    """运行时可变配置（默认模型等），持久化到 localstore"""

    def __init__(self) -> None:
        self.file = store.get_plugin_config_dir() / "config.json"
        self.default_model: str = ds_config.get_enable_models()[0]
        self.enable_md_to_pic: bool = ds_config.md_to_pic
        self.load()

    def load(self) -> None:
        if not self.file.exists():
            self.file.parent.mkdir(parents=True, exist_ok=True)
            self.save()
            return

        data = json.loads(self.file.read_text(encoding="utf-8"))
        self.default_model = data.get("default_model", self.default_model)
        self.enable_md_to_pic = data.get("enable_md_to_pic", self.enable_md_to_pic)

        if self.default_model not in ds_config.get_enable_models():
            self.default_model = ds_config.get_enable_models()[0]
            self.save()

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(
            json.dumps(
                {
                    "default_model": self.default_model,
                    "enable_md_to_pic": self.enable_md_to_pic,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


json_config = ModelConfig()
logger.debug(f"load deepseek models: {ds_config.get_enable_models()}")
