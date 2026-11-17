"""Domicilios (§7.4, RF-13, RN-18): el valor es del domiciliario, no del negocio."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.modelo import Base, Operativo
from app.shared.dinero import MontoPesos

ESTADOS_DOMICILIO = ("pendiente", "en_camino", "entregado", "cancelado")


class Domiciliario(Base, Operativo):
    """Quien lleva los pedidos. No es usuario del sistema: se elige al vender y se le liquida
    al cierre de caja."""

    __tablename__ = "domiciliarios"
    __table_args__ = (UniqueConstraint("sede_id", "nombre"),)

    nombre: Mapped[str] = mapped_column(String(80))
    telefono: Mapped[str | None] = mapped_column(String(20))
    activo: Mapped[bool] = mapped_column(default=True)


class Domicilio(Base, Operativo):
    __tablename__ = "domicilios"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente', 'en_camino', 'entregado', 'cancelado')", name="estado"
        ),
        CheckConstraint("valor >= 0", name="valor_no_negativo"),
    )

    # Siempre nace de una venta (la de mostrador o la que crea la entrega de un encargo).
    venta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ventas.id"), index=True)
    encargo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("encargos.id"), index=True)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clientes.id"), index=True)
    contacto: Mapped[str | None] = mapped_column(String(120))
    direccion: Mapped[str] = mapped_column(String(200))
    telefono: Mapped[str | None] = mapped_column(String(20))
    domiciliario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domiciliarios.id"), index=True)
    valor: Mapped[int] = mapped_column(MontoPesos())
    estado: Mapped[str] = mapped_column(String(10), default="pendiente")
    # La caja donde se cobró: ahí mismo se le entrega al domiciliario (RN-18).
    caja_sesion_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("caja_sesiones.id"), index=True)
    liquidado_en: Mapped[datetime | None]
