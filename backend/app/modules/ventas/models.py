"""Ventas (§7.4): cabecera, ítems con sus adiciones, pagos y consecutivo por sede."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.modelo import Base, Operativo
from app.shared.dinero import MontoPesos, NumericCantidad


class Consecutivo(Base):
    """Último número usado por sede y tipo de documento ("venta", "encargo"). Se toma con
    bloqueo de fila para que dos ventas simultáneas no repitan número (RN-04)."""

    __tablename__ = "consecutivos"

    sede_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sedes.id"), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20), primary_key=True)
    ultimo: Mapped[int] = mapped_column(default=0)


class Venta(Base, Operativo):
    __tablename__ = "ventas"
    __table_args__ = (
        UniqueConstraint("sede_id", "numero"),
        CheckConstraint("tipo_servicio IN ('local', 'llevar', 'domicilio')", name="tipo_servicio"),
        CheckConstraint("estado IN ('pagada', 'anulada')", name="estado"),
        CheckConstraint(
            "subtotal >= 0 AND descuento_total >= 0 AND total >= 0 AND propina >= 0 "
            "AND valor_domicilio >= 0 AND total = subtotal - descuento_total",
            name="totales",
        ),
        Index("ix_ventas_sede_fecha", "sede_id", "fecha"),
    )

    numero: Mapped[int]
    caja_sesion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("caja_sesiones.id"), index=True)
    tipo_servicio: Mapped[str] = mapped_column(String(10))
    # Los clientes llegan en la Fase 3 (#39); por ahora sin llave foránea.
    cliente_id: Mapped[uuid.UUID | None]
    subtotal: Mapped[int] = mapped_column(MontoPesos())
    descuento_total: Mapped[int] = mapped_column(MontoPesos(), default=0)
    valor_domicilio: Mapped[int] = mapped_column(MontoPesos(), default=0)
    total: Mapped[int] = mapped_column(MontoPesos())
    propina: Mapped[int] = mapped_column(MontoPesos(), default=0)
    costo_total: Mapped[int] = mapped_column(MontoPesos(), default=0)
    estado: Mapped[str] = mapped_column(String(10), default="pagada")
    descuento_motivo: Mapped[str | None] = mapped_column(String(200))
    descuento_autorizado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(server_default=func.now())
    motivo_anulacion: Mapped[str | None] = mapped_column(String(200))
    anulada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    anulada_en: Mapped[datetime | None]

    items: Mapped[list["VentaItem"]] = relationship(
        back_populates="venta", order_by="VentaItem.orden", cascade="all, delete-orphan"
    )
    pagos: Mapped[list["VentaPago"]] = relationship(
        back_populates="venta", order_by="VentaPago.orden", cascade="all, delete-orphan"
    )


class VentaItem(Base, Operativo):
    """Copia el precio del momento: si luego cambia en la carta, la venta no cambia."""

    __tablename__ = "venta_items"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint("descuento >= 0 AND descuento <= bruto", name="descuento"),
    )

    venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ventas.id"), index=True)
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productos.id"), index=True)
    cantidad: Mapped[Decimal] = mapped_column(NumericCantidad())
    precio_unitario: Mapped[int] = mapped_column(MontoPesos())
    # (precio + adiciones) × cantidad, antes de descuentos.
    bruto: Mapped[int] = mapped_column(MontoPesos())
    descuento: Mapped[int] = mapped_column(MontoPesos(), default=0)
    subtotal: Mapped[int] = mapped_column(MontoPesos())
    costo_total: Mapped[int] = mapped_column(MontoPesos(), default=0)
    nota: Mapped[str | None] = mapped_column(String(200))
    orden: Mapped[int] = mapped_column(default=0)

    venta: Mapped[Venta] = relationship(back_populates="items")
    modificadores: Mapped[list["VentaItemModificador"]] = relationship(
        back_populates="item", order_by="VentaItemModificador.orden", cascade="all, delete-orphan"
    )


class VentaItemModificador(Base, Operativo):
    """Adición por unidad del ítem: precio y costo son por el total de unidades del ítem."""

    __tablename__ = "venta_item_modificadores"

    venta_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venta_items.id"), index=True)
    modificador_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modificadores.id"))
    precio: Mapped[int] = mapped_column(MontoPesos())
    costo_total: Mapped[int] = mapped_column(MontoPesos(), default=0)
    orden: Mapped[int] = mapped_column(default=0)

    item: Mapped[VentaItem] = relationship(back_populates="modificadores")


class VentaPago(Base, Operativo):
    """Un pago por método. En efectivo puede llevar lo recibido; el cambio no es un pago."""

    __tablename__ = "venta_pagos"
    __table_args__ = (
        CheckConstraint("monto > 0", name="monto_positivo"),
        CheckConstraint("recibido IS NULL OR recibido >= monto", name="recibido_cubre"),
    )

    venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ventas.id"), index=True)
    metodo_pago_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metodos_pago.id"))
    monto: Mapped[int] = mapped_column(MontoPesos())
    recibido: Mapped[int | None] = mapped_column(MontoPesos())
    orden: Mapped[int] = mapped_column(default=0)

    venta: Mapped[Venta] = relationship(back_populates="pagos")
