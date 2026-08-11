from nonebot import get_driver, get_plugin_config
from pydantic import BaseModel, Field, field_validator

from src.providers.llm import ModelEndpoint, resolve_endpoint


class ScopedConfig(BaseModel):
    model: str | None = None
    """对话使用的模型（LLM__MODELS 中的别名）；未配置时插件不响应"""
    name: str = ""
    """自称；留空则取全局 NICKNAME 的第一个"""
    prompt: str = ""
    """追加在内置要求之后的人设"""
    history_size: int = Field(default=60, gt=0)
    """每个会话在内存里保留的消息条数"""
    context_size: int = Field(default=25, gt=0)
    """拼进提示词的最近消息条数"""
    max_text_length: int = Field(default=300, gt=0)
    """单条消息进提示词时的截断长度（字符）"""
    timeout: int = Field(default=100, gt=0)
    """请求超时（秒）"""
    temperature: float | None = Field(default=None, ge=0, le=2)
    web_search: bool = False
    """启用服务商内置的联网搜索（仅 responses / anthropic 协议支持）"""
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


class Config(BaseModel):
    chat: ScopedConfig = Field(default_factory=ScopedConfig)
    """Chat Plugin Config"""


chat_config = get_plugin_config(Config).chat


def get_endpoint() -> ModelEndpoint | None:
    """解析对话模型端点；未配置或配置有误时返回 None"""
    if not chat_config.model:
        return None
    return resolve_endpoint(chat_config.model)


def self_name() -> str:
    """机器人的自称。

    NICKNAME 在 nonebot 里是 set，取「第一个」并不稳定（字符串哈希每进程随机），
    所以排序后取定的那个，想指定就配 CHAT__NAME。
    """
    if chat_config.name:
        return chat_config.name
    return next(iter(sorted(get_driver().config.nickname)), "我")
