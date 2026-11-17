"""fase 4 índices para reportes por sede y fecha

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-16 19:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (nombre, tabla, columnas). ventas ya tiene ix_ventas_sede_fecha desde la fase 2.
INDICES = [
    ("ix_gastos_sede_fecha", "gastos", ["sede_id", "fecha"]),
    ("ix_caja_movimientos_sede_fecha", "caja_movimientos", ["sede_id", "fecha"]),
    ("ix_mermas_sede_fecha", "mermas", ["sede_id", "fecha"]),
    ("ix_movimientos_sede_fecha", "movimientos_inventario", ["sede_id", "fecha"]),
    ("ix_producciones_sede_fecha", "producciones", ["sede_id", "fecha"]),
    ("ix_encargo_abonos_sede_fecha", "encargo_abonos", ["sede_id", "fecha"]),
    ("ix_encargos_sede_cancelado", "encargos", ["sede_id", "cancelado_en"]),
    ("ix_encargos_sede_entregado", "encargos", ["sede_id", "entregado_en"]),
]


def upgrade() -> None:
    for nombre, tabla, columnas in INDICES:
        op.create_index(nombre, tabla, columnas, if_not_exists=True)


def downgrade() -> None:
    for nombre, tabla, _ in reversed(INDICES):
        op.drop_index(nombre, table_name=tabla, if_exists=True)
