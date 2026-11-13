"""Inventario (§7.3): insumos, presentaciones, lotes, libro de movimientos, faltantes, mermas,
ajustes y verificación nocturna."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.modelo import Base, Operativo
from app.shared.dinero import MontoPesos, NumericCantidad, NumericCosto

TIPOS_ITEM = ("insumo", "producto")
ORIGENES_LOTE = ("compra", "produccion", "ajuste")
TIPOS_MOVIMIENTO = (
    "compra",
    "venta",
    "consumo_produccion",
    "entrada_produccion",
    "merma",
    "ajuste",
    "reverso_anulacion",
)
MOTIVOS_MERMA = ("vencido", "danado", "error_preparacion", "degustacion")


def _en(columna: str, valores: tuple[str, ...]) -> str:
    return f"{columna} IN ({', '.join(repr(v) for v in valores)})"


class Insumo(Base, Operativo):
    __tablename__ = "insumos"
    __table_args__ = (UniqueConstraint("sede_id", "nombre"),)

    nombre: Mapped[str] = mapped_column(String(120))
    unidad_base: Mapped[str] = mapped_column(ForeignKey("unidades.codigo"))
    stock_minimo: Mapped[Decimal] = mapped_column(NumericCantidad(), default=Decimal(0))
    # Si es nulo se usa el valor general de la configuración (dias_alerta_vencimiento).
    dias_alerta_vencimiento: Mapped[int | None]
    activo: Mapped[bool] = mapped_column(default=True)

    presentaciones: Mapped[list["Presentacion"]] = relationship(
        back_populates="insumo", order_by="Presentacion.factor"
    )


class Presentacion(Base, Operativo):
    """Unidad de compra: "Bulto 50 kg" con factor 50000 convierte a gramos."""

    __tablename__ = "presentaciones"
    __table_args__ = (
        UniqueConstraint("insumo_id", "nombre"),
        CheckConstraint("factor > 0", name="factor_positivo"),
    )

    insumo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("insumos.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(80))
    factor: Mapped[Decimal] = mapped_column(NumericCantidad())
    activa: Mapped[bool] = mapped_column(default=True)

    insumo: Mapped[Insumo] = relationship(back_populates="presentaciones")


class Lote(Base, Operativo):
    """Base de PEPS y vencimientos. cantidad_disponible nunca es negativa."""

    __tablename__ = "lotes"
    __table_args__ = (
        CheckConstraint(_en("tipo_item", TIPOS_ITEM), name="tipo_item"),
        CheckConstraint(_en("origen", ORIGENES_LOTE), name="origen"),
        CheckConstraint("cantidad_inicial > 0", name="inicial_positiva"),
        CheckConstraint(
            "cantidad_disponible >= 0 AND cantidad_disponible <= cantidad_inicial",
            name="disponible_en_rango",
        ),
        CheckConstraint("costo_unitario >= 0", name="costo_no_negativo"),
        Index("ix_lotes_peps", "sede_id", "tipo_item", "item_id", "fecha_ingreso"),
    )

    tipo_item: Mapped[str] = mapped_column(String(10))
    item_id: Mapped[uuid.UUID]
    origen: Mapped[str] = mapped_column(String(12))
    origen_id: Mapped[uuid.UUID | None]
    cantidad_inicial: Mapped[Decimal] = mapped_column(NumericCantidad())
    cantidad_disponible: Mapped[Decimal] = mapped_column(NumericCantidad())
    costo_unitario: Mapped[Decimal] = mapped_column(NumericCosto())
    fecha_ingreso: Mapped[datetime] = mapped_column(server_default=func.now())
    fecha_vencimiento: Mapped[date | None]


class MovimientoInventario(Base, Operativo):
    """Libro de inventario: solo inserciones (un trigger impide UPDATE y DELETE).
    Las salidas llevan cantidad y costo_total negativos."""

    __tablename__ = "movimientos_inventario"
    __table_args__ = (
        CheckConstraint(_en("tipo", TIPOS_MOVIMIENTO), name="tipo"),
        CheckConstraint(_en("tipo_item", TIPOS_ITEM), name="tipo_item"),
        CheckConstraint("cantidad <> 0", name="cantidad_no_cero"),
        Index("ix_movimientos_item", "sede_id", "tipo_item", "item_id", "fecha"),
        Index("ix_movimientos_referencia", "referencia_tipo", "referencia_id"),
    )

    tipo: Mapped[str] = mapped_column(String(20))
    tipo_item: Mapped[str] = mapped_column(String(10))
    item_id: Mapped[uuid.UUID]
    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lotes.id"), index=True)
    cantidad: Mapped[Decimal] = mapped_column(NumericCantidad())
    costo_unitario: Mapped[Decimal] = mapped_column(NumericCosto())
    costo_total: Mapped[int] = mapped_column(MontoPesos())
    referencia_tipo: Mapped[str] = mapped_column(String(30))
    referencia_id: Mapped[uuid.UUID]
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(server_default=func.now())


class FaltanteInventario(Base, Operativo):
    """Lo que se vendió sin stock registrado (RF-16). El stock nunca queda negativo: cuando
    entra un lote del ítem se consume primero lo pendiente, con su costo real."""

    __tablename__ = "faltantes_inventario"
    __table_args__ = (
        CheckConstraint(_en("tipo_item", TIPOS_ITEM), name="tipo_item"),
        CheckConstraint("estado IN ('abierto', 'regularizado', 'anulado')", name="estado"),
        CheckConstraint("cantidad > 0 AND cantidad_pendiente >= 0", name="cantidades"),
        Index("ix_faltantes_abiertos", "sede_id", "tipo_item", "item_id", "estado"),
    )

    tipo_item: Mapped[str] = mapped_column(String(10))
    item_id: Mapped[uuid.UUID]
    cantidad: Mapped[Decimal] = mapped_column(NumericCantidad())
    cantidad_pendiente: Mapped[Decimal] = mapped_column(NumericCantidad())
    costo_estimado: Mapped[int] = mapped_column(MontoPesos())
    referencia_tipo: Mapped[str] = mapped_column(String(30))
    referencia_id: Mapped[uuid.UUID]  # la venta (Fase 2)
    estado: Mapped[str] = mapped_column(String(12), default="abierto")
    regularizado_por_mov_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("movimientos_inventario.id")
    )


class Merma(Base, Operativo):
    __tablename__ = "mermas"
    __table_args__ = (
        CheckConstraint(_en("tipo_item", TIPOS_ITEM), name="tipo_item"),
        CheckConstraint(_en("motivo", MOTIVOS_MERMA), name="motivo"),
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
    )

    tipo_item: Mapped[str] = mapped_column(String(10))
    item_id: Mapped[uuid.UUID] = mapped_column(index=True)
    lote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lotes.id"))
    cantidad: Mapped[Decimal] = mapped_column(NumericCantidad())
    motivo: Mapped[str] = mapped_column(String(20))
    nota: Mapped[str | None] = mapped_column(String(200))
    costo_total: Mapped[int] = mapped_column(MontoPesos())
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(server_default=func.now())


class AjusteInventario(Base, Operativo):
    __tablename__ = "ajustes_inventario"
    __table_args__ = (CheckConstraint(_en("tipo_item", TIPOS_ITEM), name="tipo_item"),)

    tipo_item: Mapped[str] = mapped_column(String(10))
    item_id: Mapped[uuid.UUID] = mapped_column(index=True)
    cantidad_sistema: Mapped[Decimal] = mapped_column(NumericCantidad())
    cantidad_contada: Mapped[Decimal] = mapped_column(NumericCantidad())
    diferencia: Mapped[Decimal] = mapped_column(NumericCantidad())
    # Lo vencido sin dar de baja no entra al conteo; se guarda para mostrarlo y darlo de
    # baja como merma.
    cantidad_vencida: Mapped[Decimal] = mapped_column(NumericCantidad(), server_default="0")
    costo_total: Mapped[int] = mapped_column(MontoPesos())
    motivo: Mapped[str] = mapped_column(String(200))
    aprobado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(server_default=func.now())


class VerificacionInventario(Base, Operativo):
    """Resultado de comparar Σ lotes contra Σ movimientos (RN-09)."""

    __tablename__ = "verificaciones_inventario"

    fecha: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    lotes_revisados: Mapped[int]
    diferencias: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
