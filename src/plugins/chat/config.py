import json

from nonebot import get_driver, get_plugin_config, logger
import nonebot_plugin_localstore as store
from pydantic import BaseModel, Field, field_validator
from pydantic_ai.settings import ModelSettings

from src.providers.llm import ModelEndpoint, list_models, resolve_endpoint


class ScopedConfig(BaseModel):
    model: str | None = None
    """对话使用的模型（LLM__MODELS 中的别名）；未配置时插件不响应。
    运行时可用 /llm model 切换，切换结果优先于这里"""
    name: str = ""
    """自称；留空则取全局 NICKNAME 的第一个"""
    prompt: str = ""
    """追加在内置要求之后的人设"""
    context_size: int = Field(default=25, gt=0)
    """拼进提示词的最近消息条数（缓冲大小与单条截断长度见 CHAT_HISTORY__*）"""
    timeout: int = Field(default=100, gt=0)
    """请求超时（秒）"""
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=1)
    """单次回答的最大 token 数；anthropic 协议不设时只有 4096，长回答会被截断"""
    web_search: bool = False
    """启用服务商内置的联网搜索（仅 anthropic 协议能用，见 providers.llm）"""
    max_images: int = Field(default=4, ge=0)
    """单次最多交给模型几张图片（仅对支持图片输入的模型生效），0 为不看图"""
    render_image: bool = True
    """长回答渲染成图片；关闭时发纯文本（绑定了官方机器人的群照旧走原生 markdown）"""
    send_thinking: bool = False
    """长回答排版时附上思维链"""
    blacklist: set[str] = Field(default_factory=set)
    """不接话的账号 id：群里其它机器人写在这里，免得两边你一句我一句聊起来。

    本进程自己连着的账号会自动忽略，不用往这里写。
    """

    @field_validator("name", "prompt", mode="before")
    @classmethod
    def _empty_when_unset(cls, value: object) -> object:
        # .env 里只写键名不写值表示「不配置」，取到的是 None
        return "" if value is None else value

    @field_validator("blacklist", mode="before")
    @classmethod
    def _as_id_set(cls, value: object) -> object:
        if value is None or value == "":
            return set()
        # QQ 号写成数字也收，统一按字符串比对
        if isinstance(value, list | set | tuple):
            return {str(item) for item in value}
        return value

    def model_settings(self) -> ModelSettings:
        settings = ModelSettings(timeout=self.timeout)
        if self.temperature is not None:
            settings["temperature"] = self.temperature
        if self.max_tokens is not None:
            settings["max_tokens"] = self.max_tokens
        return settings


class Config(BaseModel):
    chat: ScopedConfig = Field(default_factory=ScopedConfig)
    """Chat Plugin Config"""


chat_config = get_plugin_config(Config).chat


class RuntimeConfig:
    """运行时用 /llm model 切换的对话模型，持久化到 localstore"""

    def __init__(self) -> None:
        self.file = store.get_plugin_config_file("runtime.json")
        self.model: str | None = None
        """切换后的模型别名；没切换过时为 None，用 CHAT__MODEL"""
        self.load()

    def load(self) -> None:
        if not self.file.exists():
            return
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.opt(exception=e).error(f"对话运行时配置读取失败：{self.file}")
            return
        model = data.get("model")
        # 注册表改过、别名没了的话就当没切换过，免得插件一声不吭
        if model in list_models():
            self.model = model

    def save(self) -> None:
        self.file.write_text(
            json.dumps({"model": self.model}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


runtime = RuntimeConfig()


def current_model() -> str | None:
    """当前生效的对话模型引用"""
    return runtime.model or chat_config.model


def get_endpoint() -> ModelEndpoint | None:
    """解析对话模型端点；未配置或配置有误时返回 None"""
    if not (model := current_model()):
        return None
    return resolve_endpoint(model)


def self_name() -> str:
    """机器人的自称。

    NICKNAME 在 nonebot 里是 set，取「第一个」并不稳定（字符串哈希每进程随机），
    所以排序后取定的那个，想指定就配 CHAT__NAME。
    """
    if chat_config.name:
        return chat_config.name
    return next(iter(sorted(get_driver().config.nickname)), "我")
