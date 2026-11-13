import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.core.idempotencia import Idempotencia, idempotencia
from app.modules.compras import service
from app.modules.compras.schemas import (
    AnulacionEntrada,
    CompraCrear,
    CompraSalida,
    CuentaPorPagar,
    PagoEntrada,
    ProveedorCrear,
    ProveedorEditar,
    ProveedorSalida,
)
from app.shared.paginacion import Pagina, ParamsPagina, RangoFechas

router = APIRouter(tags=["Compras y proveedores"])

comprador = requiere("compras.crear")
gestor_proveedores = requiere("proveedores.gestionar")
lector_compras = requiere_alguno("compras.crear", "reportes.ver")
lector_proveedores = requiere_alguno("proveedores.gestionar", "compras.crear")


def _salida(db: Session, compra) -> dict:
    db.refresh(compra)
    return service.compra_salida(db, compra).model_dump(mode="json")


# --- Proveedores ----------------------------------------------------------------------------


@router.get("/proveedores", response_model=list[ProveedorSalida])
def listar_proveedores(
    incluir_inactivos: bool = Query(False),
    ctx: Contexto = Depends(lector_proveedores),
    db: Session = Depends(obtener_db),
):
    return [
        service.proveedor_salida(p) for p in service.listar_proveedores(db, ctx, incluir_inactivos)
    ]


@router.post("/proveedores", response_model=ProveedorSalida, status_code=201)
def crear_proveedor(
    datos: ProveedorCrear,
    ctx: Contexto = Depends(gestor_proveedores),
    db: Session = Depends(obtener_db),
):
    p = service.crear_proveedor(db, ctx, datos)
    db.commit()
    return service.proveedor_salida(p)


@router.patch("/proveedores/{proveedor_id}", response_model=ProveedorSalida)
def editar_proveedor(
    proveedor_id: uuid.UUID,
    datos: ProveedorEditar,
    ctx: Contexto = Depends(gestor_proveedores),
    db: Session = Depends(obtener_db),
):
    p = service.editar_proveedor(db, ctx, proveedor_id, datos)
    db.commit()
    return service.proveedor_salida(p)


# --- Compras --------------------------------------------------------------------------------


@router.get("/compras", response_model=Pagina[CompraSalida])
def listar_compras(
    params: ParamsPagina = Depends(),
    rango: RangoFechas = Depends(),
    proveedor_id: uuid.UUID | None = Query(None),
    estado_pago: str | None = Query(None, pattern="^(contado|por_pagar|pagada)$"),
    ctx: Contexto = Depends(lector_compras),
    db: Session = Depends(obtener_db),
):
    items, total = service.listar_compras(db, ctx, params, rango, proveedor_id, estado_pago)
    return Pagina(items=items, total=total, page=params.page, size=params.size)


@router.get("/compras/por-pagar", response_model=list[CuentaPorPagar])
def cuentas_por_pagar(ctx: Contexto = Depends(lector_compras), db: Session = Depends(obtener_db)):
    return service.cuentas_por_pagar(db, ctx)


@router.get("/compras/{compra_id}", response_model=CompraSalida)
def ver_compra(
    compra_id: uuid.UUID, ctx: Contexto = Depends(lector_compras), db: Session = Depends(obtener_db)
):
    return service.compra_salida(db, service.obtener_compra(db, ctx, compra_id))


@router.post("/compras", response_model=CompraSalida, status_code=201)
def crear_compra(
    datos: CompraCrear,
    ctx: Contexto = Depends(comprador),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    if (previa := idem.iniciar(db, ctx)) is not None:
        return previa
    compra = service.crear_compra(db, ctx, datos)
    db.flush()
    salida = _salida(db, compra)
    idem.guardar(db, 201, salida)
    db.commit()
    return salida


@router.post("/compras/{compra_id}/pagos", response_model=CompraSalida)
def registrar_pago(
    compra_id: uuid.UUID,
    datos: PagoEntrada,
    ctx: Contexto = Depends(comprador),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    if (previa := idem.iniciar(db, ctx)) is not None:
        return previa
    compra = service.registrar_pago(db, ctx, compra_id, datos)
    salida = _salida(db, compra)
    idem.guardar(db, 200, salida)
    db.commit()
    return salida


@router.post("/compras/{compra_id}/anular", response_model=CompraSalida)
def anular_compra(
    compra_id: uuid.UUID,
    datos: AnulacionEntrada,
    ctx: Contexto = Depends(requiere("compras.anular")),
    db: Session = Depends(obtener_db),
):
    compra = service.anular_compra(db, ctx, compra_id, datos.motivo)
    salida = _salida(db, compra)
    db.commit()
    return salida
