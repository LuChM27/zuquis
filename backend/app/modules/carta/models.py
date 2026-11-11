"""Carta y recetas (§7.2): categorías, productos, adiciones, historial de precios y recetas."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    String,
    Table,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.modelo import Base, Operativo
from app.shared.dinero import MontoPesos, NumericCantidad

TIPOS_PRODUCTO = ("preparado", "lote")

producto_modificadores = Table(
    "producto_modificadores",
    Base.metadata,
    Column("producto_id", ForeignKey("productos.id", ondelete="CASCADE"), primary_key=True),
    Column("modificador_id", ForeignKey("modificadores.id", ondelete="CASCADE"), primary_key=True),
)


class Categoria(Base, Operativo):
    __tablename__ = "categorias"
    __table_args__ = (UniqueConstraint("sede_id", "nombre"),)

    nombre: Mapped[str] = mapped_column(String(80))
    orden: Mapped[int] = mapped_column(default=0)
    icono: Mapped[str | None] = mapped_column(String(40))
    activa: Mapped[bool] = mapped_column(default=True)


class Producto(Base, Operativo):
    __tablename__ = "productos"
    __table_args__ = (
        UniqueConstraint("sede_id", "nombre"),
        CheckConstraint("tipo IN ('preparado', 'lote')", name="tipo"),
        CheckConstraint("precio >= 0", name="precio_no_negativo"),
    )

    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categorias.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(12))
    precio: Mapped[int] = mapped_column(MontoPesos())
    foto_url: Mapped[str | None] = mapped_column(String(300))
    disponible: Mapped[bool] = mapped_column(default=True)
    activo: Mapped[bool] = mapped_column(default=True)
    stock_minimo: Mapped[Decimal] = mapped_column(NumericCantidad(), default=Decimal(0))
    dias_vida_util: Mapped[int | None]

    modificadores: Mapped[list["Modificador"]] = relationship(
        secondary=producto_modificadores, order_by="Modificador.nombre"
    )


class Modificador(Base, Operativo):
    """Adiciones con precio (queso mozzarella, bola de helado). Pueden tener receta propia."""

    __tablename__ = "modificadores"
    __table_args__ = (
        UniqueConstraint("sede_id", "nombre"),
        CheckConstraint("precio >= 0", name="precio_no_negativo"),
    )

    nombre: Mapped[str] = mapped_column(String(80))
    precio: Mapped[int] = mapped_column(MontoPesos())
    activo: Mapped[bool] = mapped_column(default=True)


class PrecioHistorial(Base, Operativo):
    __tablename__ = "precios_historial"

    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productos.id"), index=True)
    precio_anterior: Mapped[int | None] = mapped_column(MontoPesos())
    precio_nuevo: Mapped[int] = mapped_column(MontoPesos())
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(server_default=func.now())


class Receta(Base, Operativo):
    """Versionada: editar una receta crea una versión nueva; las pasadas no se tocan, así los
    costos ya registrados no cambian."""

    __tablename__ = "recetas"
    __table_args__ = (
        CheckConstraint(
            "(producto_id IS NULL) <> (modificador_id IS NULL)", name="producto_o_modificador"
        ),
        CheckConstraint("rendimiento > 0", name="rendimiento_positivo"),
        # Una sola versión vigente por producto y por modificador.
        Index(
            "uq_recetas_producto_vigente",
            "producto_id",
            unique=True,
            postgresql_where=text("vigente AND producto_id IS NOT NULL"),
        ),
        Index(
            "uq_recetas_modificador_vigente",
            "modificador_id",
            unique=True,
            postgresql_where=text("vigente AND modificador_id IS NOT NULL"),
        ),
    )

    producto_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("productos.id"), index=True)
    modificador_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("modificadores.id"), index=True
    )
    rendimiento: Mapped[Decimal] = mapped_column(NumericCantidad())
    version: Mapped[int]
    vigente: Mapped[bool] = mapped_column(default=True)

    items: Mapped[list["RecetaItem"]] = relationship(
        back_populates="receta", cascade="all, delete-orphan", order_by="RecetaItem.orden"
    )


class RecetaItem(Base, Operativo):
    __tablename__ = "receta_items"
    __table_args__ = (
        UniqueConstraint("receta_id", "insumo_id"),
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
    )

    receta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recetas.id", ondelete="CASCADE"), index=True
    )
    insumo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("insumos.id"), index=True)
    cantidad: Mapped[Decimal] = mapped_column(NumericCantidad())  # en la unidad base del insumo
    orden: Mapped[int] = mapped_column(default=0)

    receta: Mapped[Receta] = relationship(back_populates="items")
