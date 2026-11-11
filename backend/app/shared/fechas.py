"""Fechas: se guardan en UTC y se muestran en America/Bogota (RNF-07)."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.core.config import obtener_config


def ahora() -> datetime:
    return datetime.now(UTC)


def zona() -> ZoneInfo:
    return ZoneInfo(obtener_config().zona_horaria)


def a_local(momento: datetime) -> datetime:
    return momento.astimezone(zona())


def hoy() -> date:
    """Fecha de hoy en la zona del negocio (vencimientos, producción)."""
    return ahora().astimezone(zona()).date()
