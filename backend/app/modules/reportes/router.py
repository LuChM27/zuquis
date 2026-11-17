import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere_alguno
from app.modules.caja.service import caja_abierta
from app.modules.reportes.esquemas import Reporte
from app.modules.reportes.periodo import SIN_CAJA, Periodo, resolver_periodo
from app.modules.reportes.tablas import REPORTES
from app.shared.errores import NoEncontrado, SinPermiso

router = APIRouter(prefix="/reportes", tags=["Reportes"])

lector = requiere_alguno("reportes.ver", "reportes.ver_caja_propia", "reportes.ver_inventario")

# Qué permisos abren cada reporte. El cajero (ver_caja_propia) solo ve su caja abierta.
ACCESO: dict[str, frozenset[str]] = {
    "ventas": frozenset({"reportes.ver", "reportes.ver_caja_propia"}),
}


def periodo_de(
    db: Session,
    ctx: Contexto,
    tipo: str,
    desde: date | None,
    hasta: date | None,
    sede_id: uuid.UUID | None,
) -> Periodo:
    """Valida el acceso al reporte y arma su periodo (el del cajero, limitado a su caja)."""
    if tipo not in ACCESO:
        raise NoEncontrado("el reporte", tipo)
    if not ACCESO[tipo] & ctx.permisos:
        raise SinPermiso(next(iter(sorted(ACCESO[tipo]))))
    p = resolver_periodo(db, ctx, desde, hasta, sede_id)
    if "reportes.ver" in ctx.permisos or "reportes.ver_caja_propia" not in ACCESO[tipo]:
        return p
    sesion = caja_abierta(db, ctx.sede_id)
    return Periodo(
        sede_id=ctx.sede_id,
        desde=p.desde,
        hasta=p.hasta,
        caja_sesion_id=sesion.id if sesion else SIN_CAJA,
    )


@router.get("/{tipo}", response_model=Reporte)
def ver_reporte(
    tipo: str,
    desde: date | None = Query(None, description="Fecha inicial ISO (aaaa-mm-dd)"),
    hasta: date | None = Query(None, description="Fecha final ISO, inclusive"),
    sede_id: uuid.UUID | None = Query(None),
    ctx: Contexto = Depends(lector),
    db: Session = Depends(obtener_db),
):
    p = periodo_de(db, ctx, tipo, desde, hasta, sede_id)
    return REPORTES[tipo](db, p)
