import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.modelo import Base, ConId


class Idempotencia(Base, ConId):
    """Respuestas guardadas por Idempotency-Key (sección 9)."""

    __tablename__ = "idempotencia"
    __table_args__ = (UniqueConstraint("usuario_id", "clave"),)

    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"))
    clave: Mapped[str] = mapped_column(String(100))
    ruta: Mapped[str] = mapped_column(String(200))
    hash_cuerpo: Mapped[str] = mapped_column(String(64))
    estado_http: Mapped[int | None]
    respuesta: Mapped[dict[str, Any] | None]
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now())
    expira_en: Mapped[datetime] = mapped_column(index=True)
