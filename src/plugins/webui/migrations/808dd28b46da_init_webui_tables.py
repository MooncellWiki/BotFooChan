"""init webui tables

迁移 ID: 808dd28b46da
父迁移:
创建时间: 2026-11-11 08:27:11.707855

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "808dd28b46da"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("webui",)
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return
    op.create_table(
        "webui_admin",
        sa.Column("login", sa.String(length=64), nullable=False),
        sa.Column("note", sa.String(length=256), nullable=False),
        sa.Column("added_by", sa.String(length=128), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("login", name=op.f("pk_webui_admin")),
        info={"bind_key": "webui"},
    )


def downgrade(name: str = "") -> None:
    if name:
        return
    op.drop_table("webui_admin")
