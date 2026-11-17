"""fase 4 fecha límite de pago en compras

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-16 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("compras", sa.Column("fecha_limite_pago", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("compras", "fecha_limite_pago")
