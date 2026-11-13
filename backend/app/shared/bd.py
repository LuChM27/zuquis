"""Utilidades de base de datos comunes a los servicios."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.shared.errores import Conflicto


def guardar_unico(
    db: Session, codigo: str = "NOMBRE_DUPLICADO", mensaje: str = "Ya existe uno con ese nombre."
) -> None:
    """flush que convierte una violación de unicidad en un 409 claro. La transacción la revierte
    la dependencia de la petición."""
    try:
        db.flush()
    except IntegrityError as exc:
        raise Conflicto(codigo, mensaje) from exc
