import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.core.idempotencia import Idempotencia, idempotencia
from app.modules.encargos import service
from app.modules.encargos.schemas import (
    AbonoEntrada,
    AnulacionAbono,
    CambioEstado,
    CancelacionEntrada,
    ConteoDia,
    EncargoCrear,
    EncargoEditar,
    EncargoSalida,
    EntregaEntrada,
    Estado,
    GastoDecoracionEntrada,
)
from app.shared.errores import ErrorNegocio, SinPermiso
from app.shared.fechas import hoy
from app.shared.paginacion import Pagina, ParamsPagina, RangoFechas

router = APIRouter(tags=["Encargos"])

operador = requiere("encargos.crear")
LECTURA = ("encargos.crear", "encargos.devolver_abono", "reportes.ver")
lector = requiere_alguno(*LECTURA)
registrador_gastos = requiere_alguno("gastos.crear", "gastos.crear_caja")


def gastos_de_encargo(ctx: Contexto = Depends(registrador_gastos)) -> Contexto:
    """Registra gastos y además puede ver el encargo (la respuesta es el encargo completo)."""
    if not any(ctx.puede(p) for p in LECTURA):
        raise SinPermiso(" | ".join(LECTURA))
    return ctx


def _con_idempotencia(db, ctx, idem, status, operacion):
    """Las operaciones con dinero no se duplican si el navegador reintenta."""
    if (previa := idem.iniciar(db, ctx)) is not None:
        return previa
    salida = service.salida(db, ctx, operacion()).model_dump(mode="json")
    idem.guardar(db, status, salida)
    db.commit()
    return salida


@router.get("/encargos", response_model=Pagina[EncargoSalida])
def listar_encargos(
    params: ParamsPagina = Depends(),
    rango: RangoFechas = Depends(),
    estado: Estado | None = Query(None),
    cliente_id: uuid.UUID | None = Query(None),
    q: str | None = Query(None, description="Número, descripción o cliente"),
    ctx: Contexto = Depends(lector),
    db: Session = Depends(obtener_db),
):
    """Encargos por fecha de entrega; `desde` y `hasta` filtran ese día, no el de creación."""
    items, total = service.listar(db, ctx, params, rango.desde, rango.hasta, estado, cliente_id, q)
    return Pagina(items=items, total=total, page=params.page, size=params.size)


@router.get("/encargos/conteo", response_model=list[ConteoDia])
def conteo_encargos(
    rango: RangoFechas = Depends(),
    ctx: Contexto = Depends(lector),
    db: Session = Depends(obtener_db),
):
    """Cuántos encargos se entregan cada día del rango (por defecto, los próximos 7 días)."""
    desde = rango.desde or hoy()
    hasta = rango.hasta or desde + timedelta(days=6)
    if not 0 <= (hasta - desde).days <= 92:
        raise ErrorNegocio("VALIDACION", "El rango debe ser de máximo tres meses.", status=422)
    return service.conteo(db, ctx, desde, hasta)


@router.post("/encargos", response_model=EncargoSalida, status_code=201)
def crear_encargo(
    datos: EncargoCrear,
    ctx: Contexto = Depends(operador),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    """Crea el encargo con su número consecutivo. Si trae abono inicial, la caja debe estar
    abierta."""
    return _con_idempotencia(db, ctx, idem, 201, lambda: service.crear(db, ctx, datos))


@router.get("/encargos/{encargo_id}", response_model=EncargoSalida)
def ver_encargo(
    encargo_id: uuid.UUID, ctx: Contexto = Depends(lector), db: Session = Depends(obtener_db)
):
    return service.salida(db, ctx, service.obtener(db, ctx, encargo_id))


@router.patch("/encargos/{encargo_id}", response_model=EncargoSalida)
def editar_encargo(
    encargo_id: uuid.UUID,
    datos: EncargoEditar,
    ctx: Contexto = Depends(operador),
    db: Session = Depends(obtener_db),
):
    """Solo mientras está pendiente (RN-23): después responde ENCARGO_EN_PRODUCCION."""
    encargo = service.editar(db, ctx, encargo_id, datos)
    db.commit()
    return service.salida(db, ctx, encargo)


@router.post("/encargos/{encargo_id}/estado", response_model=EncargoSalida)
def cambiar_estado(
    encargo_id: uuid.UUID,
    datos: CambioEstado,
    ctx: Contexto = Depends(operador),
    db: Session = Depends(obtener_db),
):
    """pendiente → en_produccion → listo. Entregar y cancelar tienen su propia operación."""
    encargo = service.cambiar_estado(db, ctx, encargo_id, datos.estado)
    db.commit()
    return service.salida(db, ctx, encargo)


@router.post("/encargos/{encargo_id}/abonos", response_model=EncargoSalida, status_code=201)
def registrar_abono(
    encargo_id: uuid.UUID,
    datos: AbonoEntrada,
    ctx: Contexto = Depends(operador),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    """El abono entra a la caja abierta (RN-20) y no puede superar el saldo (RN-19)."""
    return _con_idempotencia(db, ctx, idem, 201, lambda: service.abonar(db, ctx, encargo_id, datos))


@router.post("/encargos/{encargo_id}/gastos", response_model=EncargoSalida, status_code=201)
def registrar_gasto_decoracion(
    encargo_id: uuid.UUID,
    datos: GastoDecoracionEntrada,
    ctx: Contexto = Depends(gastos_de_encargo),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    """Gasto de materiales de decoración ligado al encargo; cuenta en Gastos con la categoría
    "Materiales de decoración". Quien solo registra gastos de caja, solo desde la caja."""
    return _con_idempotencia(
        db, ctx, idem, 201, lambda: service.registrar_gasto(db, ctx, encargo_id, datos)
    )


@router.post("/encargos/{encargo_id}/abonos/{abono_id}/anular", response_model=EncargoSalida)
def anular_abono(
    encargo_id: uuid.UUID,
    abono_id: uuid.UUID,
    datos: AnulacionAbono,
    ctx: Contexto = Depends(requiere("encargos.anular_abono")),
    db: Session = Depends(obtener_db),
):
    encargo = service.anular_abono(db, ctx, encargo_id, abono_id, datos.motivo)
    db.commit()
    return service.salida(db, ctx, encargo)


@router.post("/encargos/{encargo_id}/entregar", response_model=EncargoSalida)
def entregar_encargo(
    encargo_id: uuid.UUID,
    datos: EntregaEntrada,
    ctx: Contexto = Depends(operador),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    """Cobra el saldo, crea la venta, descuenta el inventario y aplica los abonos (RN-21)."""
    return _con_idempotencia(
        db, ctx, idem, 200, lambda: service.entregar(db, ctx, encargo_id, datos)
    )


@router.post("/encargos/{encargo_id}/cancelar", response_model=EncargoSalida)
def cancelar_encargo(
    encargo_id: uuid.UUID,
    datos: CancelacionEntrada | None = None,
    ctx: Contexto = Depends(requiere("encargos.devolver_abono")),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    """Sin cuerpo devuelve todo lo abonado (RN-22). Retener exige decisión, monto y motivo."""
    return _con_idempotencia(
        db,
        ctx,
        idem,
        200,
        lambda: service.cancelar(db, ctx, encargo_id, datos or CancelacionEntrada()),
    )
