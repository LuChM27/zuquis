import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.core.idempotencia import Idempotencia, idempotencia
from app.modules.caja import cierre, service
from app.modules.caja.schemas import (
    AbrirCaja,
    CerrarCaja,
    EstadoCaja,
    MovimientoManual,
    MovimientoSalida,
    SesionDetalle,
    SesionResumen,
    SesionSalida,
    VistaCierre,
)
from app.shared.paginacion import Pagina, ParamsPagina

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


# --- Cierre e historial (#32) ---------------------------------------------------------------

cerrador = requiere("caja.cerrar")
lector_historial = requiere_alguno("caja.cerrar", "reportes.ver", "reportes.ver_caja_propia")


@router.get("/caja/actual/cierre", response_model=VistaCierre)
def vista_cierre(ctx: Contexto = Depends(cerrador), db: Session = Depends(obtener_db)):
    """Lo esperado por método, de dónde sale el efectivo y el resumen del turno."""
    return cierre.vista_previa(db, ctx)


@router.post("/caja/cerrar", response_model=SesionDetalle)
def cerrar_caja(
    datos: CerrarCaja, ctx: Contexto = Depends(cerrador), db: Session = Depends(obtener_db)
):
    sesion = cierre.cerrar(db, ctx, datos)
    db.commit()
    return cierre.detalle(db, ctx, sesion.id)


@router.get("/caja/sesiones", response_model=Pagina[SesionResumen])
def historial(
    params: ParamsPagina = Depends(),
    ctx: Contexto = Depends(lector_historial),
    db: Session = Depends(obtener_db),
):
    items, total = cierre.listar(db, ctx, params)
    return Pagina(items=items, total=total, page=params.page, size=params.size)


@router.get("/caja/sesiones/{sesion_id}", response_model=SesionDetalle)
def ver_sesion(
    sesion_id: uuid.UUID,
    ctx: Contexto = Depends(lector_historial),
    db: Session = Depends(obtener_db),
):
    return cierre.detalle(db, ctx, sesion_id)
