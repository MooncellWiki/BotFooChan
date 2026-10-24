from pydantic import BaseModel, Field


class Config(BaseModel):
    zssm_ai_text_model: str | None = None
    """文本模型引用：LLM__MODELS 中的别名，或 '服务商:模型名'"""
    zssm_ai_vl_model: str | None = None
    """视觉模型引用"""
    zssm_ai_check_model: str | None = None
    """审查模型引用（缺省时跳过 system prompt 泄露审查）"""
    zssm_ai_web_search: bool = False
    """文本模型启用服务商内置的联网搜索（仅 anthropic 协议能用，见 providers.llm）"""
    zssm_context_size: int = Field(default=8, ge=0)
    """预先附带的、被解释消息之前的聊天记录条数；更早的由模型用工具自己翻，0 为不附带"""

    # PDF处理设置
    zssm_pdf_max_size: int = 10 * 1024 * 1024  # 10MB
    zssm_pdf_max_pages: int = 50  # 最大处理页数
    zssm_pdf_max_chars: int = 300000  # 最大字符数

    # 网页处理设置
    zssm_web_max_chars: int = 30000
    """网页正文的最大字符数；inner_text 连导航栏页脚一起抓，不截断能把上下文撑爆"""
