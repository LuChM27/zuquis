"""Producción por lote (§7.3, RF-29, RN-07)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.modelo import Base, Operativo
from app.shared.dinero import MontoPesos, NumericCantidad


class Produccion(Base, Operativo):
    __tablename__ = "producciones"
    __table_args__ = (CheckConstraint("cantidad_producida > 0", name="cantidad_positiva"),)

    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productos.id"), index=True)
    receta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recetas.id"))
    cantidad_producida: Mapped[Decimal] = mapped_column(NumericCantidad())
    costo_total: Mapped[int] = mapped_column(MontoPesos())
    lote_resultante_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lotes.id"))
    responsable_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(server_default=func.now())
    anulada: Mapped[bool] = mapped_column(default=False)
    anulada_en: Mapped[datetime | None]
    anulada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(String(200))


# Reportes por sede y fecha (fase 4, migración 0010).
Index("ix_producciones_sede_fecha", Produccion.sede_id, Produccion.fecha)
