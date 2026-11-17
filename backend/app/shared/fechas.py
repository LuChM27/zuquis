"""Fechas: se guardan en UTC y se muestran en America/Bogota (RNF-07)."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.core.config import obtener_config

_fijo: datetime | None = None


def fijar_ahora(momento: datetime | None) -> None:
    """Fija la hora que devuelve ``ahora()`` (pruebas de varios días y semillas de ejemplo).
    ``None`` vuelve al reloj real. Funciona aunque el módulo haya importado ``ahora`` por
    nombre, porque la función lee esta variable en cada llamada."""
    global _fijo
    _fijo = momento.astimezone(UTC) if momento else None


def ahora() -> datetime:
    return _fijo or datetime.now(UTC)


def zona() -> ZoneInfo:
    return ZoneInfo(obtener_config().zona_horaria)


def a_local(momento: datetime) -> datetime:
    return momento.astimezone(zona())


def hoy() -> date:
    """Fecha de hoy en la zona del negocio (vencimientos, producción)."""
    return ahora().astimezone(zona()).date()
