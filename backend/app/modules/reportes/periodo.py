"""Periodo de un reporte: sede y rango de fechas locales (America/Bogota), ``hasta`` inclusive."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.core.deps import Contexto, permisos_en_sede
from app.shared.errores import ErrorNegocio, SinPermiso
from app.shared.fechas import hoy, zona

MAX_DIAS = 366
# Sesión que no existe: el cajero sin caja abierta ve el reporte vacío.
SIN_CAJA = uuid.UUID(int=0)


@dataclass(frozen=True)
class Periodo:
    sede_id: uuid.UUID
    desde: date
    hasta: date
    caja_sesion_id: uuid.UUID | None = None

    def limites(self) -> tuple[datetime, datetime]:
        """[inicio del día ``desde``, inicio del día siguiente a ``hasta``) en hora local."""
        inicio = datetime.combine(self.desde, time(), tzinfo=zona())
        fin = datetime.combine(self.hasta + timedelta(days=1), time(), tzinfo=zona())
        return inicio, fin

    @property
    def dias(self) -> int:
        return (self.hasta - self.desde).days + 1


def _rango_invalido(mensaje: str) -> ErrorNegocio:
    return ErrorNegocio("RANGO_INVALIDO", mensaje, status=422)


def resolver_periodo(
    db: Session,
    ctx: Contexto,
    desde: date | None,
    hasta: date | None,
    sede_id: uuid.UUID | None,
) -> Periodo:
    desde = desde or hoy()
    hasta = hasta or max(desde, hoy())
    if desde > hasta:
        raise _rango_invalido("La fecha inicial no puede ser posterior a la final.")
    if (hasta - desde).days + 1 > MAX_DIAS:
        raise _rango_invalido("El rango no puede pasar de un año.")
    otra_sede = sede_id is not None and sede_id != ctx.sede_id
    if otra_sede and "reportes.ver" not in permisos_en_sede(db, ctx.usuario_id, sede_id):
        raise SinPermiso("reportes.ver")
    return Periodo(sede_id=sede_id or ctx.sede_id, desde=desde, hasta=hasta)
