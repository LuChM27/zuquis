"""Encargos y abonos (§7.5, RF-34 a RF-39, RN-19 a RN-23)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.modelo import Base, Operativo
from app.shared.dinero import MontoPesos, NumericCantidad

if TYPE_CHECKING:
    from app.modules.gastos.models import Gasto

ESTADOS = ("pendiente", "en_produccion", "listo", "entregado", "cancelado")
ACTIVOS = ("pendiente", "en_produccion", "listo")


class Encargo(Base, Operativo):
    __tablename__ = "encargos"
    __table_args__ = (
        UniqueConstraint("sede_id", "numero"),
        CheckConstraint(
            "estado IN ('pendiente', 'en_produccion', 'listo', 'entregado', 'cancelado')",
            name="estado",
        ),
        CheckConstraint("tipo_entrega IN ('recoge', 'domicilio')", name="tipo_entrega"),
        CheckConstraint("total > 0", name="total_positivo"),
        CheckConstraint(
            "decision_cancelacion IS NULL OR decision_cancelacion IN "
            "('devuelve_total', 'devuelve_parcial', 'retiene')",
            name="decision",
        ),
        CheckConstraint("monto_devuelto >= 0 AND monto_retenido >= 0", name="montos_cancelacion"),
        Index("ix_encargos_sede_entrega", "sede_id", "fecha_entrega"),
    )

    numero: Mapped[int]
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clientes.id"), index=True)
    descripcion: Mapped[str] = mapped_column(String(200))
    fecha_entrega: Mapped[datetime]
    tipo_entrega: Mapped[str] = mapped_column(String(10), default="recoge")
    direccion_entrega: Mapped[str | None] = mapped_column(String(200))
    observaciones: Mapped[str | None] = mapped_column(String(500))
    total: Mapped[int] = mapped_column(MontoPesos())
    estado: Mapped[str] = mapped_column(String(15), default="pendiente")
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    # Al entregar (RN-21).
    venta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ventas.id"), index=True)
    entregado_en: Mapped[datetime | None]
    # Al cancelar (RN-22). Lo retenido es ingreso por cancelación, no venta.
    decision_cancelacion: Mapped[str | None] = mapped_column(String(20))
    monto_devuelto: Mapped[int] = mapped_column(MontoPesos(), default=0)
    monto_retenido: Mapped[int] = mapped_column(MontoPesos(), default=0)
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(200))
    cancelado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    cancelado_en: Mapped[datetime | None]

    items: Mapped[list["EncargoItem"]] = relationship(
        back_populates="encargo", order_by="EncargoItem.orden", cascade="all, delete-orphan"
    )
    abonos: Mapped[list["EncargoAbono"]] = relationship(
        back_populates="encargo", order_by="EncargoAbono.fecha"
    )
    # Gastos de materiales de decoración; se cargan en lote al listar.
    gastos: Mapped[list["Gasto"]] = relationship(
        order_by="(Gasto.fecha, Gasto.creado_en)", lazy="selectin", viewonly=True
    )


class EncargoItem(Base, Operativo):
    """Con producto de la carta (descuenta inventario al entregar) o personalizado, solo con
    descripción y precio. La decoración es opcional: referencia y valor por el ítem completo
    (no por unidad); solo se cobra, no toca inventario."""

    __tablename__ = "encargo_items"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint("precio >= 0", name="precio_no_negativo"),
        CheckConstraint(
            "(decoracion IS NULL) = (decoracion_precio IS NULL)", name="decoracion_completa"
        ),
        CheckConstraint(
            "decoracion_precio IS NULL OR decoracion_precio > 0", name="decoracion_positiva"
        ),
    )

    encargo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("encargos.id"), index=True)
    producto_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("productos.id"))
    descripcion: Mapped[str] = mapped_column(String(200))
    cantidad: Mapped[Decimal] = mapped_column(NumericCantidad())
    precio: Mapped[int] = mapped_column(MontoPesos())
    orden: Mapped[int] = mapped_column(default=0)
    decoracion: Mapped[str | None] = mapped_column(String(200))
    decoracion_precio: Mapped[int | None] = mapped_column(MontoPesos())

    encargo: Mapped[Encargo] = relationship(back_populates="items")


class EncargoAbono(Base, Operativo):
    """Cada abono entra a la caja abierta al recibirlo (RN-20)."""

    __tablename__ = "encargo_abonos"
    __table_args__ = (
        CheckConstraint("monto > 0", name="monto_positivo"),
        CheckConstraint("estado IN ('vigente', 'anulado')", name="estado"),
    )

    encargo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("encargos.id"), index=True)
    monto: Mapped[int] = mapped_column(MontoPesos())
    metodo_pago_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metodos_pago.id"))
    caja_sesion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("caja_sesiones.id"), index=True)
    estado: Mapped[str] = mapped_column(String(10), default="vigente")
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(server_default=func.now())
    motivo_anulacion: Mapped[str | None] = mapped_column(String(200))
    anulado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    anulado_en: Mapped[datetime | None]

    encargo: Mapped[Encargo] = relationship(back_populates="abonos")
