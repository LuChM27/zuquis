import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.core.idempotencia import Idempotencia, idempotencia
from app.modules.inventario import operaciones, service
from app.modules.inventario.models import Insumo, Presentacion
from app.modules.inventario.schemas import (
    AjusteCrear,
    AjusteSalida,
    InsumoCrear,
    InsumoEditar,
    InsumoSalida,
    MermaCrear,
    MermaSalida,
    MotivoMerma,
    PresentacionCrear,
    PresentacionEditar,
    PresentacionSalida,
    TipoItem,
)
from app.shared.paginacion import Pagina, ParamsPagina, RangoFechas

router = APIRouter(tags=["Inventario"])

gestor_insumos = requiere("insumos.gestionar")
# Varias pantallas necesitan la lista de insumos: inventario, compras, recetas y producción.
lector_insumos = requiere_alguno(
    "inventario.ver", "insumos.gestionar", "compras.crear", "recetas.editar", "produccion.crear"
)


def _insumo_salida(insumo: Insumo) -> InsumoSalida:
    return InsumoSalida.model_validate(insumo, from_attributes=True)


@router.get("/insumos", response_model=list[InsumoSalida])
def listar_insumos(
    incluir_inactivos: bool = Query(False),
    ctx: Contexto = Depends(lector_insumos),
    db: Session = Depends(obtener_db),
):
    return [_insumo_salida(i) for i in service.listar_insumos(db, ctx, incluir_inactivos)]


@router.post("/insumos", response_model=InsumoSalida, status_code=201)
def crear_insumo(
    datos: InsumoCrear, ctx: Contexto = Depends(gestor_insumos), db: Session = Depends(obtener_db)
):
    insumo = service.crear_insumo(db, ctx, datos)
    db.commit()
    return _insumo_salida(insumo)


@router.get("/insumos/{insumo_id}", response_model=InsumoSalida)
def ver_insumo(
    insumo_id: uuid.UUID, ctx: Contexto = Depends(lector_insumos), db: Session = Depends(obtener_db)
):
    return _insumo_salida(service.obtener_insumo(db, ctx, insumo_id))


@router.patch("/insumos/{insumo_id}", response_model=InsumoSalida)
def editar_insumo(
    insumo_id: uuid.UUID,
    datos: InsumoEditar,
    ctx: Contexto = Depends(gestor_insumos),
    db: Session = Depends(obtener_db),
):
    insumo = service.editar_insumo(db, ctx, insumo_id, datos)
    db.commit()
    db.refresh(insumo)
    return _insumo_salida(insumo)


@router.post(
    "/insumos/{insumo_id}/presentaciones", response_model=PresentacionSalida, status_code=201
)
def crear_presentacion(
    insumo_id: uuid.UUID,
    datos: PresentacionCrear,
    ctx: Contexto = Depends(gestor_insumos),
    db: Session = Depends(obtener_db),
):
    p = service.crear_presentacion(db, ctx, insumo_id, datos)
    db.commit()
    return PresentacionSalida.model_validate(p, from_attributes=True)


@router.patch(
    "/insumos/{insumo_id}/presentaciones/{presentacion_id}", response_model=PresentacionSalida
)
def editar_presentacion(
    insumo_id: uuid.UUID,
    presentacion_id: uuid.UUID,
    datos: PresentacionEditar,
    ctx: Contexto = Depends(gestor_insumos),
    db: Session = Depends(obtener_db),
):
    p: Presentacion = service.editar_presentacion(db, ctx, insumo_id, presentacion_id, datos)
    db.commit()
    return PresentacionSalida.model_validate(p, from_attributes=True)


# --- Mermas y ajustes (#22) -----------------------------------------------------------------


@router.get("/mermas", response_model=Pagina[MermaSalida])
def listar_mermas(
    params: ParamsPagina = Depends(),
    rango: RangoFechas = Depends(),
    tipo_item: TipoItem | None = Query(None),
    item_id: uuid.UUID | None = Query(None),
    motivo: MotivoMerma | None = Query(None),
    ctx: Contexto = Depends(requiere_alguno("inventario.merma", "inventario.ver")),
    db: Session = Depends(obtener_db),
):
    items, total = operaciones.listar_mermas(db, ctx, params, rango, tipo_item, item_id, motivo)
    return Pagina(items=items, total=total, page=params.page, size=params.size)


@router.post("/mermas", response_model=MermaSalida, status_code=201)
def registrar_merma(
    datos: MermaCrear,
    ctx: Contexto = Depends(requiere("inventario.merma")),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    if (previa := idem.iniciar(db, ctx)) is not None:
        return previa
    merma = operaciones.registrar_merma(db, ctx, datos)
    nombre = operaciones.nombre_item(db, ctx, merma.tipo_item, merma.item_id)
    salida = operaciones.merma_salida(merma, nombre).model_dump(mode="json")
    idem.guardar(db, 201, salida)
    db.commit()
    return salida


@router.get("/ajustes", response_model=Pagina[AjusteSalida])
def listar_ajustes(
    params: ParamsPagina = Depends(),
    rango: RangoFechas = Depends(),
    item_id: uuid.UUID | None = Query(None),
    ctx: Contexto = Depends(requiere_alguno("inventario.ajustar", "inventario.ver")),
    db: Session = Depends(obtener_db),
):
    items, total = operaciones.listar_ajustes(db, ctx, params, rango, item_id)
    return Pagina(items=items, total=total, page=params.page, size=params.size)


@router.post("/ajustes", response_model=AjusteSalida, status_code=201)
def registrar_ajuste(
    datos: AjusteCrear,
    ctx: Contexto = Depends(requiere("inventario.ajustar")),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    if (previa := idem.iniciar(db, ctx)) is not None:
        return previa
    ajuste = operaciones.registrar_ajuste(db, ctx, datos)
    salida = operaciones.ajuste_salida(ajuste).model_dump(mode="json")
    idem.guardar(db, 201, salida)
    db.commit()
    return salida
