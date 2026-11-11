from typing import Any

from sqlalchemy import Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.modelo import Base, ConId, ConSede, ConTiempos, Operativo


class Sede(Base, ConId, ConTiempos):
    __tablename__ = "sedes"

    nombre: Mapped[str] = mapped_column(String(120))
    direccion: Mapped[str | None] = mapped_column(String(200))
    telefono: Mapped[str | None] = mapped_column(String(40))
    activa: Mapped[bool] = mapped_column(default=True)


class Configuracion(Base, ConId, ConSede, ConTiempos):
    """Parámetros por sede. El esquema de cada clave vive en configuracion/schemas.py."""

    __tablename__ = "configuracion"
    __table_args__ = (UniqueConstraint("sede_id", "clave"),)

    clave: Mapped[str] = mapped_column(String(80))
    valor: Mapped[dict[str, Any]]


class MetodoPago(Base, Operativo):
    __tablename__ = "metodos_pago"
    __table_args__ = (
        # Un solo método de efectivo activo por sede: el arqueo le suma la base inicial.
        Index(
            "uq_metodos_pago_efectivo_activo",
            "sede_id",
            unique=True,
            postgresql_where=text("es_efectivo AND activo"),
        ),
        UniqueConstraint("sede_id", "nombre"),
    )

    nombre: Mapped[str] = mapped_column(String(60))
    es_efectivo: Mapped[bool] = mapped_column(default=False)
    # Hay transferencias que llegan a cuentas personales de los dueños (decisión en #1).
    titular: Mapped[str] = mapped_column(String(10), default="negocio")
    cuenta_puc: Mapped[str | None] = mapped_column(String(10))
    activo: Mapped[bool] = mapped_column(default=True)
    orden: Mapped[int] = mapped_column(default=0)


class Unidad(Base, ConId):
    """Unidades base de inventario (g, ml, und). Catálogo global."""

    __tablename__ = "unidades"

    codigo: Mapped[str] = mapped_column(String(10), unique=True)
    nombre: Mapped[str] = mapped_column(String(40))
