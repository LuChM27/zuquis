"""Caja (§7.4): sesiones, libro de dinero de solo inserción y arqueos al cerrar.

La caja define el día contable (RNF-07): cada venta, abono, gasto o pago desde caja queda ligado
a la sesión abierta en el momento de registrarlo.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.modelo import Base, Operativo
from app.shared.dinero import MontoPesos

TIPOS_MOVIMIENTO_CAJA = (
    "venta",
    "propina",
    "domicilio",
    "pago_domiciliario",
    "abono",
    "saldo_encargo",
    "devolucion_abono",
    "gasto",
    "pago_compra",
    "entrada_manual",
    "salida_manual",
    "reverso_anulacion",
)


def _en(columna: str, valores: tuple[str, ...]) -> str:
    return f"{columna} IN ({', '.join(repr(v) for v in valores)})"


class CajaSesion(Base, Operativo):
    __tablename__ = "caja_sesiones"
    __table_args__ = (
        CheckConstraint("estado IN ('abierta', 'cerrada')", name="estado"),
        CheckConstraint("base_inicial >= 0", name="base_no_negativa"),
        # Una sola caja abierta por sede (CAJA_YA_ABIERTA).
        Index(
            "uq_caja_sesiones_abierta_por_sede",
            "sede_id",
            unique=True,
            postgresql_where=text("estado = 'abierta'"),
        ),
    )

    abierta_por: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    abierta_en: Mapped[datetime] = mapped_column(server_default=func.now())
    base_inicial: Mapped[int] = mapped_column(MontoPesos())
    cerrada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    cerrada_en: Mapped[datetime | None]
    estado: Mapped[str] = mapped_column(String(10), default="abierta")
    observacion: Mapped[str | None] = mapped_column(String(500))


class CajaMovimiento(Base, Operativo):
    """Libro de dinero: solo inserciones (un trigger impide UPDATE y DELETE). Las salidas llevan
    monto negativo."""

    __tablename__ = "caja_movimientos"
    __table_args__ = (
        CheckConstraint(_en("tipo", TIPOS_MOVIMIENTO_CAJA), name="tipo"),
        CheckConstraint("monto <> 0", name="monto_no_cero"),
        Index("ix_caja_movimientos_referencia", "referencia_tipo", "referencia_id"),
    )

    caja_sesion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("caja_sesiones.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    metodo_pago_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metodos_pago.id"))
    monto: Mapped[int] = mapped_column(MontoPesos())
    referencia_tipo: Mapped[str | None] = mapped_column(String(30))
    referencia_id: Mapped[uuid.UUID | None]
    motivo: Mapped[str | None] = mapped_column(String(200))
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(server_default=func.now())


class CajaArqueo(Base, Operativo):
    """Una fila por método al cerrar: lo esperado, lo contado y la diferencia tal cual (RN-14)."""

    __tablename__ = "caja_arqueos"
    __table_args__ = (
        CheckConstraint("diferencia = contado - esperado", name="diferencia"),
        CheckConstraint("contado >= 0", name="contado_no_negativo"),
    )

    caja_sesion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("caja_sesiones.id"), index=True)
    metodo_pago_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metodos_pago.id"))
    esperado: Mapped[int] = mapped_column(MontoPesos())
    contado: Mapped[int] = mapped_column(MontoPesos())
    diferencia: Mapped[int] = mapped_column(MontoPesos())


# Reportes por sede y fecha (fase 4, migración 0010).
Index("ix_caja_movimientos_sede_fecha", CajaMovimiento.sede_id, CajaMovimiento.fecha)
