"""Base declarativa y campos comunes de las tablas (sección 7 de la especificación).

Toda tabla operativa lleva id (UUID), sede_id, creado_en, creado_por y actualizado_en.
Los montos son BIGINT y las cantidades/costos NUMERIC (ver app.shared.dinero). Float está
prohibido; tests/test_modelo.py falla si aparece.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, MetaData, Uuid, event, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, declared_attr, mapped_column

CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)
    type_annotation_map = {
        datetime: DateTime(timezone=True),
        uuid.UUID: Uuid,
        dict[str, Any]: JSONB,
    }


class ConId:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class ConTiempos:
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class ConCreador:
    @declared_attr
    def creado_por(cls) -> Mapped[uuid.UUID | None]:  # noqa: N805
        return mapped_column(ForeignKey("usuarios.id"), nullable=True)


class ConSede:
    @declared_attr
    def sede_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
        return mapped_column(ForeignKey("sedes.id"), index=True)


class Operativo(ConId, ConSede, ConTiempos, ConCreador):
    """Campos comunes de las tablas operativas."""


# El usuario autenticado se guarda en session.info["usuario_id"] (ver app.core.deps) y se
# copia a creado_por de todo objeto nuevo que lo tenga vacío.
@event.listens_for(Session, "before_flush")
def _llenar_creado_por(session: Session, _flush_context, _instances) -> None:
    usuario_id = session.info.get("usuario_id")
    if usuario_id is None:
        return
    for obj in session.new:
        if hasattr(obj, "creado_por") and obj.creado_por is None:
            obj.creado_por = usuario_id
