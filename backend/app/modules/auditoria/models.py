import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.modelo import Base, ConId


class Auditoria(Base, ConId):
    """Rastro de cambios sensibles. Solo inserción: un trigger impide UPDATE y DELETE."""

    __tablename__ = "auditoria"

    sede_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sedes.id"), index=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"), index=True)
    accion: Mapped[str] = mapped_column(String(40))
    entidad: Mapped[str] = mapped_column(String(60), index=True)
    entidad_id: Mapped[str | None] = mapped_column(String(64))
    antes: Mapped[dict[str, Any] | None]
    despues: Mapped[dict[str, Any] | None]
    fecha: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    ip: Mapped[str | None] = mapped_column(String(45))
