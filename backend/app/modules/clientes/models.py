"""Clientes (§7.5, RF-40): para encargos y domicilios, con su historial."""

from datetime import datetime

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.modelo import Base, Operativo


class Cliente(Base, Operativo):
    __tablename__ = "clientes"
    # El teléfono no es único: dos personas pueden compartirlo. Al repetirlo se advierte.
    __table_args__ = (Index("ix_clientes_sede_telefono", "sede_id", "telefono"),)

    nombre: Mapped[str] = mapped_column(String(120))
    # Solo dígitos, sin indicativo del país (ver clientes.service.normalizar_telefono).
    telefono: Mapped[str | None] = mapped_column(String(20))
    direccion: Mapped[str | None] = mapped_column(String(200))
    notas: Mapped[str | None] = mapped_column(String(500))
    # Ley 1581 de 2012: el cliente autorizó guardar y usar sus datos, y cuándo.
    autoriza_datos: Mapped[bool] = mapped_column(default=False)
    autorizo_en: Mapped[datetime | None]
    activo: Mapped[bool] = mapped_column(default=True)
