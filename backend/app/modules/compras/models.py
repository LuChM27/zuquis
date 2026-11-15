"""Proveedores, compras con lotes y cuentas por pagar (§7.3, RF-24 a RF-26)."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, ForeignKey, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.modelo import Base, Operativo
from app.shared.dinero import MontoPesos, NumericCantidad, NumericCosto

ESTADOS_PAGO = ("contado", "por_pagar", "pagada")

proveedor_insumos = Table(
    "proveedor_insumos",
    Base.metadata,
    Column("proveedor_id", ForeignKey("proveedores.id", ondelete="CASCADE"), primary_key=True),
    Column("insumo_id", ForeignKey("insumos.id", ondelete="CASCADE"), primary_key=True),
)


class Proveedor(Base, Operativo):
    __tablename__ = "proveedores"

    nombre: Mapped[str] = mapped_column(String(120))
    nit_o_cedula: Mapped[str | None] = mapped_column(String(30))
    telefono: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(default=True)

    insumos: Mapped[list["Insumo"]] = relationship(  # noqa: F821
        "Insumo", secondary=proveedor_insumos, order_by="Insumo.nombre"
    )


class Compra(Base, Operativo):
    __tablename__ = "compras"
    __table_args__ = (
        CheckConstraint("estado_pago IN ('contado', 'por_pagar', 'pagada')", name="estado_pago"),
        CheckConstraint("total >= 0", name="total_no_negativo"),
    )

    proveedor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("proveedores.id"), index=True)
    fecha: Mapped[date]
    numero_factura_proveedor: Mapped[str | None] = mapped_column(String(60))
    total: Mapped[int] = mapped_column(MontoPesos())
    estado_pago: Mapped[str] = mapped_column(String(12))
    soporte_url: Mapped[str | None] = mapped_column(String(300))
    anulada: Mapped[bool] = mapped_column(default=False)
    anulada_en: Mapped[datetime | None]
    anulada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(String(200))

    items: Mapped[list["CompraItem"]] = relationship(
        back_populates="compra", order_by="CompraItem.orden"
    )
    pagos: Mapped[list["PagoCompra"]] = relationship(
        back_populates="compra", order_by="PagoCompra.fecha"
    )


class CompraItem(Base, Operativo):
    """Cada ítem crea un lote del insumo en su unidad base."""

    __tablename__ = "compra_items"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint("costo_total >= 0", name="costo_no_negativo"),
    )

    compra_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compras.id"), index=True)
    insumo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("insumos.id"), index=True)
    presentacion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("presentaciones.id"))
    cantidad: Mapped[Decimal] = mapped_column(NumericCantidad())  # en la presentación
    cantidad_base: Mapped[Decimal] = mapped_column(NumericCantidad())
    costo_total: Mapped[int] = mapped_column(MontoPesos())
    costo_unitario: Mapped[Decimal] = mapped_column(NumericCosto())  # por unidad base
    fecha_vencimiento: Mapped[date | None]
    lote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lotes.id"))
    orden: Mapped[int] = mapped_column(default=0)

    compra: Mapped[Compra] = relationship(back_populates="items")


class PagoCompra(Base, Operativo):
    """Pago a un proveedor. Si salió de la caja, queda ligado a la sesión abierta (#28)."""

    __tablename__ = "pagos_compra"
    __table_args__ = (CheckConstraint("monto > 0", name="monto_positivo"),)

    compra_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("compras.id"), index=True)
    fecha: Mapped[datetime] = mapped_column(server_default=func.now())
    monto: Mapped[int] = mapped_column(MontoPesos())
    metodo_pago_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metodos_pago.id"))
    caja_sesion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("caja_sesiones.id"))

    compra: Mapped[Compra] = relationship(back_populates="pagos")
