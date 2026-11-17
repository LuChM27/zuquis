"""fase 3 decoración en encargos

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-16 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIA = "Materiales de decoración"


def upgrade() -> None:
    op.add_column("encargo_items", sa.Column("decoracion", sa.String(length=200), nullable=True))
    op.add_column("encargo_items", sa.Column("decoracion_precio", sa.BigInteger(), nullable=True))
    op.create_check_constraint(
        op.f("ck_encargo_items_decoracion_completa"),
        "encargo_items",
        "(decoracion IS NULL) = (decoracion_precio IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_encargo_items_decoracion_positiva"),
        "encargo_items",
        "decoracion_precio IS NULL OR decoracion_precio > 0",
    )
    op.add_column("gastos", sa.Column("encargo_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_gastos_encargo_id_encargos"), "gastos", "encargos", ["encargo_id"], ["id"]
    )
    op.create_index(op.f("ix_gastos_encargo_id"), "gastos", ["encargo_id"], unique=False)
    op.get_bind().execute(
        sa.text(
            "INSERT INTO categorias_gasto (id, sede_id, nombre, cuenta_puc, activa) "
            "SELECT gen_random_uuid(), s.id, CAST(:nombre AS varchar), '5195', true FROM sedes s "
            "WHERE NOT EXISTS (SELECT 1 FROM categorias_gasto c "
            "WHERE c.sede_id = s.id AND c.nombre = CAST(:nombre AS varchar))"
        ),
        {"nombre": CATEGORIA},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM categorias_gasto c WHERE c.nombre = :nombre "
            "AND NOT EXISTS (SELECT 1 FROM gastos g WHERE g.categoria_id = c.id)"
        ),
        {"nombre": CATEGORIA},
    )
    op.drop_index(op.f("ix_gastos_encargo_id"), table_name="gastos")
    op.drop_constraint(op.f("fk_gastos_encargo_id_encargos"), "gastos", type_="foreignkey")
    op.drop_column("gastos", "encargo_id")
    op.drop_constraint(op.f("ck_encargo_items_decoracion_positiva"), "encargo_items", type_="check")
    op.drop_constraint(op.f("ck_encargo_items_decoracion_completa"), "encargo_items", type_="check")
    op.drop_column("encargo_items", "decoracion_precio")
    op.drop_column("encargo_items", "decoracion")
