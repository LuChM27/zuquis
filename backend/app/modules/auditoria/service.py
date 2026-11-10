"""Registro de auditoría. Se llama desde los servicios, dentro de la misma transacción: si la
operación falla, tampoco queda el registro."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.modules.auditoria.models import Auditoria

if TYPE_CHECKING:
    from app.core.deps import Contexto


def _a_json(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {k: _a_json(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set, frozenset)):
        return [_a_json(v) for v in valor]
    if isinstance(valor, (uuid.UUID, Decimal)):
        return str(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Enum):
        return valor.value
    return valor


def instantanea(obj: Any, campos: list[str]) -> dict[str, Any]:
    """Estado de un objeto para guardar en antes/después. Nunca incluir hashes ni claves."""
    return {c: _a_json(getattr(obj, c)) for c in campos}


def auditar(
    db: Session,
    ctx: "Contexto | None",
    accion: str,
    entidad: str,
    entidad_id: Any = None,
    antes: dict[str, Any] | None = None,
    despues: dict[str, Any] | None = None,
    *,
    usuario_id: uuid.UUID | None = None,
    sede_id: uuid.UUID | None = None,
    ip: str | None = None,
) -> None:
    db.add(
        Auditoria(
            sede_id=sede_id or (ctx.sede_id if ctx else None),
            usuario_id=usuario_id or (ctx.usuario_id if ctx else None),
            accion=accion,
            entidad=entidad,
            entidad_id=str(entidad_id) if entidad_id is not None else None,
            antes=_a_json(antes) if antes is not None else None,
            despues=_a_json(despues) if despues is not None else None,
            ip=ip or (ctx.ip if ctx else None),
        )
    )
