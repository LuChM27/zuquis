from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.core.idempotencia import Idempotencia, idempotencia
from app.modules.caja import service
from app.modules.caja.schemas import (
    AbrirCaja,
    EstadoCaja,
    MovimientoManual,
    MovimientoSalida,
    SesionSalida,
)

router = APIRouter(tags=["Caja"])

lector_caja = requiere_alguno("caja.abrir", "caja.cerrar", "caja.movimientos", "ventas.crear")


@router.get("/caja/actual", response_model=EstadoCaja)
def caja_actual(ctx: Contexto = Depends(lector_caja), db: Session = Depends(obtener_db)):
    """Estado de la caja de la sede: abierta desde, responsable y esperado por método en vivo."""
    return service.estado(db, ctx)


@router.post("/caja/abrir", response_model=SesionSalida, status_code=201)
def abrir_caja(
    datos: AbrirCaja,
    ctx: Contexto = Depends(requiere("caja.abrir")),
    db: Session = Depends(obtener_db),
):
    sesion = service.abrir(db, ctx, datos.base_inicial)
    db.commit()
    return service.sesion_salida(db, sesion)


@router.get("/caja/actual/movimientos", response_model=list[MovimientoSalida])
def movimientos_actuales(ctx: Contexto = Depends(lector_caja), db: Session = Depends(obtener_db)):
    sesion = service.caja_abierta(db, ctx.sede_id)
    return service.movimientos_de(db, ctx, sesion.id) if sesion else []


@router.post("/caja/movimientos", response_model=MovimientoSalida, status_code=201)
def registrar_movimiento(
    datos: MovimientoManual,
    ctx: Contexto = Depends(requiere("caja.movimientos")),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    if (previa := idem.iniciar(db, ctx)) is not None:
        return previa
    mov = service.movimiento_manual(db, ctx, datos)
    salida = service.movimiento_salida(db, mov).model_dump(mode="json")
    idem.guardar(db, 201, salida)
    db.commit()
    return salida
