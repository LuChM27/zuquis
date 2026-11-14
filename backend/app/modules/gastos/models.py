"""Gastos y categorías de gasto con cuenta PUC (§7.4, RF-21 a RF-23)."""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.modelo import Base, Operativo
from app.shared.dinero import MontoPesos

# Categorías iniciales (docs/puc-propuesta.md). Cortesías y mermas no van: el sistema las
# calcula por su costo.
CATEGORIAS_INICIALES = (
    ("Arriendo del local", "5120"),
    ("Servicios públicos (agua, energía, gas)", "5135"),
    ("Internet y teléfono", "5135"),
    ("Transporte y fletes", "5135"),
    ("Honorarios (contador, asesorías)", "5110"),
    ("Pagos a personal", "5105"),
    ("Impuestos, licencias y permisos", "5115"),
    ("Mantenimiento y reparaciones", "5145"),
    ("Aseo y cafetería", "5195"),
    ("Papelería", "5195"),
    ("Publicidad", "5235"),
    ("Comisiones y gastos bancarios", "5305"),
    ("Otros gastos", "5195"),
)


class CategoriaGasto(Base, Operativo):
    __tablename__ = "categorias_gasto"
    __table_args__ = (UniqueConstraint("sede_id", "nombre"),)

    nombre: Mapped[str] = mapped_column(String(80))
    cuenta_puc: Mapped[str | None] = mapped_column(String(10))
    activa: Mapped[bool] = mapped_column(default=True)


class Gasto(Base, Operativo):
    __tablename__ = "gastos"
    __table_args__ = (
        CheckConstraint("monto > 0", name="monto_positivo"),
        CheckConstraint("fuente IN ('caja', 'banco', 'duenos')", name="fuente"),
        CheckConstraint("estado IN ('registrado', 'anulado')", name="estado"),
        CheckConstraint(
            "(fuente = 'caja') = (caja_sesion_id IS NOT NULL)", name="caja_si_fuente_caja"
        ),
    )

    fecha: Mapped[date]
    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categorias_gasto.id"), index=True)
    descripcion: Mapped[str] = mapped_column(String(200))
    monto: Mapped[int] = mapped_column(MontoPesos())
    metodo_pago_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metodos_pago.id"))
    fuente: Mapped[str] = mapped_column(String(10))
    caja_sesion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("caja_sesiones.id"))
    proveedor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proveedores.id"))
    soporte_url: Mapped[str | None] = mapped_column(String(300))
    estado: Mapped[str] = mapped_column(String(10), default="registrado")
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(String(200))
    anulado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    anulado_en: Mapped[datetime | None]
