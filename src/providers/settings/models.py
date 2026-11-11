from datetime import datetime
from typing import Any

from nonebot_plugin_orm import Model
from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class SettingsDoc(Model):
    """一个配置段（如 chat、llm）的完整文档，密钥已加密"""

    __tablename__ = "settings_doc"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[str] = mapped_column(String(128))


class AuditLog(Model):
    """配置和管理操作的审计记录：谁、什么时候、改了什么"""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor: Mapped[str] = mapped_column(String(128))
    """操作人：``github:<用户名>``（管理后台）、``<适配器>:<用户 id>``（聊天指令）
    或 ``system``"""
    entity: Mapped[str] = mapped_column(String(128), index=True)
    """``settings:<配置段>``、``admin``、``bison`` 之类"""
    action: Mapped[str] = mapped_column(String(32))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
