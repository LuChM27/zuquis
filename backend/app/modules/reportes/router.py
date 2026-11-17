import uuid
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.modules.caja.service import caja_abierta
from app.modules.configuracion.service import valor
from app.modules.reportes.dashboard import Dashboard, dashboard
from app.modules.reportes.esquemas import Reporte
from app.modules.reportes.exportar import a_pdf, a_xlsx
from app.modules.reportes.graficos import Grupo, grupo
from app.modules.reportes.periodo import SIN_CAJA, Periodo, resolver_periodo
from app.modules.reportes.puc import reporte_puc
from app.modules.reportes.tablas import REPORTES as REPORTES_VENTAS
from app.modules.reportes.tablas_dinero import REPORTES_DINERO
from app.modules.reportes.tablas_inventario import REPORTES_INVENTARIO
from app.shared.errores import NoEncontrado, SinPermiso

router = APIRouter(prefix="/reportes", tags=["Reportes"])

lector = requiere_alguno("reportes.ver", "reportes.ver_caja_propia", "reportes.ver_inventario")

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_JSON = TypeAdapter(dict[str, Any])

REPORTES = REPORTES_VENTAS | REPORTES_DINERO | REPORTES_INVENTARIO | {"puc": reporte_puc}

_TODO = frozenset({"reportes.ver"})
_CAJA = frozenset({"reportes.ver", "reportes.ver_caja_propia"})
_INVENTARIO = frozenset({"reportes.ver", "reportes.ver_inventario"})
# Qué permisos abren cada reporte. El cajero (ver_caja_propia) solo ve su caja abierta.
ACCESO: dict[str, frozenset[str]] = {
    "ventas": _CAJA,
    "cierres": _TODO,
    "gastos": _TODO,
    "flujo-caja": _TODO,
    "propinas": _TODO,
    "domicilios": _TODO,
    "descuentos-cortesias": _TODO,
    "ingresos-cancelacion": _TODO,
    "utilidad-productos": _TODO,
    "inventario-valorizado": _INVENTARIO,
    "mermas": _INVENTARIO,
    "puc": _TODO,
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


@router.get("/dashboard", response_model=Dashboard)
def ver_dashboard(
    ctx: Contexto = Depends(requiere("reportes.ver")), db: Session = Depends(obtener_db)
):
    return dashboard(db, ctx)


@router.get("/graficos")
def ver_graficos(
    grupo_: Grupo = Query(..., alias="grupo"),
    desde: date | None = Query(None),
    hasta: date | None = Query(None),
    sede_id: uuid.UUID | None = Query(None),
    ctx: Contexto = Depends(lector),
    db: Session = Depends(obtener_db),
) -> JSONResponse:
    """Datos de un grupo de la galería (se pide cada grupo cuando aparece en pantalla)."""
    p = resolver_periodo(db, ctx, desde, hasta, sede_id)
    # Pydantic en modo JSON deja los Decimal como string (jsonable_encoder los haría float).
    return JSONResponse(_JSON.dump_python(grupo(db, p, grupo_, ctx.permisos), mode="json"))


@router.get("/{tipo}", response_model=Reporte)
def ver_reporte(
    tipo: str,
    desde: date | None = Query(None, description="Fecha inicial ISO (aaaa-mm-dd)"),
    hasta: date | None = Query(None, description="Fecha final ISO, inclusive"),
    sede_id: uuid.UUID | None = Query(None),
    formato: Literal["json", "xlsx", "pdf"] = Query("json"),
    ctx: Contexto = Depends(lector),
    db: Session = Depends(obtener_db),
):
    if formato != "json" and not ctx.puede("reportes.exportar"):
        raise SinPermiso("reportes.exportar")
    p = periodo_de(db, ctx, tipo, desde, hasta, sede_id)
    r = REPORTES[tipo](db, p)
    if formato == "json":
        return r
    negocio = valor(db, p.sede_id, "negocio").nombre
    nombre = f"zuquis-{tipo}-{p.desde}-{p.hasta}.{formato}"
    contenido, tipo_mime = (
        (a_xlsx(r, negocio), XLSX) if formato == "xlsx" else (a_pdf(r, negocio), "application/pdf")
    )
    return Response(
        contenido,
        media_type=tipo_mime,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
