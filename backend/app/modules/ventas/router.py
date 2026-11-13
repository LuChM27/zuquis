import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.core.idempotencia import Idempotencia, idempotencia
from app.modules.ventas import service
from app.modules.ventas.schemas import VentaCrear, VentaSalida
from app.shared.paginacion import Pagina, ParamsPagina, RangoFechas

router = APIRouter(tags=["Ventas"])

lector_ventas = requiere_alguno("ventas.crear", "ventas.anular", "reportes.ver")


@router.post("/ventas", response_model=VentaSalida, status_code=201)
def crear_venta(
    datos: VentaCrear,
    ctx: Contexto = Depends(requiere("ventas.crear")),
    idem: Idempotencia = Depends(idempotencia(requerida=True)),
    db: Session = Depends(obtener_db),
):
    """Registra la venta completa en una transacción. Idempotency-Key obligatorio: un
    reintento del POS por una falla de red devuelve la misma venta sin duplicarla."""
    if (previa := idem.iniciar(db, ctx)) is not None:
        return previa
    venta = service.crear(db, ctx, datos)
    salida = service.salida(db, venta).model_dump(mode="json")
    idem.guardar(db, 201, salida)
    db.commit()
    return salida


@router.get("/ventas", response_model=Pagina[VentaSalida])
def listar_ventas(
    params: ParamsPagina = Depends(),
    rango: RangoFechas = Depends(),
    caja_sesion_id: uuid.UUID | None = Query(None),
    estado: Literal["pagada", "anulada"] | None = Query(None),
    ctx: Contexto = Depends(lector_ventas),
    db: Session = Depends(obtener_db),
):
    items, total = service.listar(db, ctx, params, rango, caja_sesion_id, estado)
    return Pagina(items=items, total=total, page=params.page, size=params.size)


@router.get("/ventas/{venta_id}", response_model=VentaSalida)
def ver_venta(
    venta_id: uuid.UUID, ctx: Contexto = Depends(lector_ventas), db: Session = Depends(obtener_db)
):
    return service.salida(db, service.obtener(db, ctx, venta_id))
