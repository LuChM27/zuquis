import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.modelo import Base, ConId, ConTiempos


class Usuario(Base, ConId, ConTiempos):
    __tablename__ = "usuarios"

    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    pin_hash: Mapped[str | None] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(default=True)
    ultimo_acceso: Mapped[datetime | None]
    intentos_fallidos: Mapped[int] = mapped_column(default=0)
    bloqueado_hasta: Mapped[datetime | None]


class SesionRefresh(Base, ConId):
    """Token de renovación. Solo se guarda su hash y se rota en cada uso.

    Los tokens de un mismo inicio de sesión comparten familia_id: si se reutiliza uno ya
    rotado (posible robo), se revoca la familia completa.
    """

    __tablename__ = "sesiones_refresh"

    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"), index=True)
    sede_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sedes.id"))
    familia_id: Mapped[uuid.UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    creado_en: Mapped[datetime]
    expira_en: Mapped[datetime]
    revocado_en: Mapped[datetime | None]
    reemplazado_por: Mapped[uuid.UUID | None]
