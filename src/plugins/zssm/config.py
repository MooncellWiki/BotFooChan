from pydantic import BaseModel


class Config(BaseModel):
    zssm_ai_text_model: str | None = None
    """文本模型引用：LLM__MODELS 中的别名，或 '服务商:模型名'"""
    zssm_ai_vl_model: str | None = None
    """视觉模型引用"""
    zssm_ai_check_model: str | None = None
    """审查模型引用（缺省时跳过 system prompt 泄露审查）"""

    # PDF处理设置
    zssm_pdf_max_size: int = 10 * 1024 * 1024  # 10MB
    zssm_pdf_max_pages: int = 50  # 最大处理页数
    zssm_pdf_max_chars: int = 300000  # 最大字符数
