from nonebot import get_plugin_config
from pydantic import BaseModel, ConfigDict, Field

from src.providers.settings import register


class Config(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    zssm_ai_model: str | None = Field(
        default=None, json_schema_extra={"model_ref": True}
    )
    """模型引用：模型注册表里的别名，或 '服务商:模型名'。
    图片直接交给它看，所以要选支持图片输入的模型（DeepSeek 官方只有 Flash 系）"""
    zssm_ai_web_search: bool = False
    """启用服务商内置的联网搜索（仅 anthropic 协议能用，见 providers.llm）"""
    zssm_context_size: int = Field(default=8, ge=0)
    """预先附带的、被解释消息之前的聊天记录条数；更早的由模型用工具自己翻，0 为不附带"""

    zssm_pdf_max_size: int = 10 * 1024 * 1024
    """PDF 的最大体积（字节），默认 10MB"""
    zssm_pdf_max_pages: int = 50
    """PDF 最多处理多少页"""
    zssm_pdf_max_chars: int = 300000
    """PDF 正文的最大字符数"""

    zssm_web_max_chars: int = 30000
    """网页正文的最大字符数；inner_text 连导航栏页脚一起抓，不截断能把上下文撑爆"""


plugin_config = register(
    "zssm",
    Config,
    title="zssm（这是什么）",
    description="用 AI 解释群友发的「未知」内容",
    env=lambda: get_plugin_config(Config),
)
