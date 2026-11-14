import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.core.idempotencia import Idempotencia, idempotencia
from app.modules.gastos import service
from app.modules.gastos.schemas import (
    AnulacionEntrada,
    CategoriaCrear,
    CategoriaEditar,
    CategoriaSalida,
    Fuente,
    GastoCrear,
    GastoSalida,
)
from app.shared.paginacion import Pagina, ParamsPagina, RangoFechas

router = APIRouter(tags=["Gastos"])

registrador = requiere_alguno("gastos.crear", "gastos.crear_caja")
lector = requiere_alguno("gastos.crear", "gastos.crear_caja", "reportes.ver")
editor_categorias = requiere("config.editar")


@router.get("/categorias-gasto", response_model=list[CategoriaSalida])
def listar_categorias(
    incluir_inactivas: bool = Query(False),
    ctx: Contexto = Depends(lector),
    db: Session = Depends(obtener_db),
):
    return service.listar_categorias(db, ctx, incluir_inactivas)


@router.post("/categorias-gasto", response_model=CategoriaSalida, status_code=201)
def crear_categoria(
    datos: CategoriaCrear,
    ctx: Contexto = Depends(editor_categorias),
    db: Session = Depends(obtener_db),
):
    c = service.crear_categoria(db, ctx, datos)
    db.commit()
    return c


@router.patch("/categorias-gasto/{categoria_id}", response_model=CategoriaSalida)
def editar_categoria(
    categoria_id: uuid.UUID,
    datos: CategoriaEditar,
    ctx: Contexto = Depends(editor_categorias),
    db: Session = Depends(obtener_db),
):
    c = service.editar_categoria(db, ctx, categoria_id, datos)
    db.commit()
    return c


@router.get("/gastos", response_model=Pagina[GastoSalida])
def listar_gastos(
    params: ParamsPagina = Depends(),
    rango: RangoFechas = Depends(),
    fuente: Fuente | None = Query(None),
    categoria_id: uuid.UUID | None = Query(None),
    estado: Literal["registrado", "anulado"] | None = Query(None),
    ctx: Contexto = Depends(lector),
    db: Session = Depends(obtener_db),
):
    items, total = service.listar(db, ctx, params, rango, fuente, categoria_id, estado)
    return Pagina(items=items, total=total, page=params.page, size=params.size)


@router.post("/gastos", response_model=GastoSalida, status_code=201)
def crear_gasto(
    datos: GastoCrear,
    ctx: Contexto = Depends(registrador),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    if (previa := idem.iniciar(db, ctx)) is not None:
        return previa
    salida = service.salida(db, service.crear(db, ctx, datos)).model_dump(mode="json")
    idem.guardar(db, 201, salida)
    db.commit()
    return salida


@router.post("/gastos/{gasto_id}/anular", response_model=GastoSalida)
def anular_gasto(
    gasto_id: uuid.UUID,
    datos: AnulacionEntrada,
    ctx: Contexto = Depends(requiere("gastos.anular")),
    db: Session = Depends(obtener_db),
):
    g = service.anular(db, ctx, gasto_id, datos.motivo)
    db.commit()
    return service.salida(db, g)
