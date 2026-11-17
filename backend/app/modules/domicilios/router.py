import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.modules.caja import service as caja
from app.modules.domicilios import service
from app.modules.domicilios.schemas import (
    DomiciliarioCrear,
    DomiciliarioEditar,
    DomiciliarioSalida,
    DomicilioCambio,
    DomicilioSalida,
    LiquidacionTurno,
    LiquidarEntrada,
)
from app.shared.errores import Conflicto
from app.shared.fechas import hoy
from app.shared.paginacion import RangoFechas

router = APIRouter(tags=["Domicilios"])

operador = requiere_alguno("ventas.crear", "encargos.crear")
lector = requiere_alguno("ventas.crear", "encargos.crear", "caja.cerrar", "reportes.ver")
cerrador = requiere("caja.cerrar")


@router.get("/domiciliarios", response_model=list[DomiciliarioSalida])
def listar_domiciliarios(
    incluir_inactivos: bool = Query(False),
    ctx: Contexto = Depends(lector),
    db: Session = Depends(obtener_db),
):
    return service.listar_domiciliarios(db, ctx, incluir_inactivos)


@router.post("/domiciliarios", response_model=DomiciliarioSalida, status_code=201)
def crear_domiciliario(
    datos: DomiciliarioCrear, ctx: Contexto = Depends(operador), db: Session = Depends(obtener_db)
):
    d = service.crear_domiciliario(db, ctx, datos)
    db.commit()
    return d


@router.patch("/domiciliarios/{domiciliario_id}", response_model=DomiciliarioSalida)
def editar_domiciliario(
    domiciliario_id: uuid.UUID,
    datos: DomiciliarioEditar,
    ctx: Contexto = Depends(operador),
    db: Session = Depends(obtener_db),
):
    d = service.editar_domiciliario(db, ctx, domiciliario_id, datos)
    db.commit()
    return d


@router.get("/domicilios", response_model=list[DomicilioSalida])
def listar_domicilios(
    rango: RangoFechas = Depends(),
    estado: Literal["pendiente", "en_camino", "entregado", "cancelado"] | None = Query(None),
    domiciliario_id: uuid.UUID | None = Query(None),
    ctx: Contexto = Depends(lector),
    db: Session = Depends(obtener_db),
):
    """Domicilios del rango (por defecto, hoy), del más reciente al más antiguo."""
    desde = rango.desde or hoy()
    hasta = rango.hasta or max(desde, hoy())
    return service.listar(db, ctx, desde, hasta, estado, domiciliario_id)


@router.patch("/domicilios/{domicilio_id}/estado", response_model=DomicilioSalida)
def cambiar_domicilio(
    domicilio_id: uuid.UUID,
    datos: DomicilioCambio,
    ctx: Contexto = Depends(operador),
    db: Session = Depends(obtener_db),
):
    """Cambia el estado (pendiente, en camino, entregado) o reasigna el domiciliario."""
    salida = service.cambiar(db, ctx, domicilio_id, datos)
    db.commit()
    return salida


@router.get("/caja/actual/domicilios", response_model=LiquidacionTurno)
def liquidacion_actual(ctx: Contexto = Depends(lector), db: Session = Depends(obtener_db)):
    """Paso 1 del cierre: cuánto se cobró por domicilios y cuánto falta entregarle a cada uno."""
    sesion = caja.caja_abierta(db, ctx.sede_id)
    if sesion is None:
        raise Conflicto("CAJA_CERRADA", "No hay caja abierta.")
    return service.liquidacion(db, sesion)


@router.post("/caja/liquidar-domicilios", response_model=LiquidacionTurno)
def liquidar_domicilios(
    datos: LiquidarEntrada, ctx: Contexto = Depends(cerrador), db: Session = Depends(obtener_db)
):
    """Entrega al domiciliario lo cobrado por sus domicilios: sale de la caja como
    `pago_domiciliario` y sus domicilios quedan liquidados (RN-18)."""
    salida = service.liquidar(db, ctx, datos)
    db.commit()
    return salida
