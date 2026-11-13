import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.core.idempotencia import Idempotencia, idempotencia
from app.modules.produccion import service
from app.modules.produccion.schemas import (
    AnulacionEntrada,
    ProduccionCrear,
    ProduccionSalida,
    ProduccionVistaPrevia,
)
from app.shared.paginacion import Pagina, ParamsPagina, RangoFechas

router = APIRouter(tags=["Producción"])


@router.get("/producciones", response_model=Pagina[ProduccionSalida])
def listar(
    params: ParamsPagina = Depends(),
    rango: RangoFechas = Depends(),
    producto_id: uuid.UUID | None = Query(None),
    ctx: Contexto = Depends(requiere_alguno("produccion.crear", "inventario.ver")),
    db: Session = Depends(obtener_db),
):
    items, total = service.listar(db, ctx, params, rango, producto_id)
    return Pagina(items=items, total=total, page=params.page, size=params.size)


@router.post("/producciones", response_model=ProduccionSalida, status_code=201)
def crear(
    datos: ProduccionCrear,
    ctx: Contexto = Depends(requiere("produccion.crear")),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    if (previa := idem.iniciar(db, ctx)) is not None:
        return previa
    p = service.crear(db, ctx, datos)
    salida = service.salida(db, p).model_dump(mode="json")
    idem.guardar(db, 201, salida)
    db.commit()
    return salida


@router.post("/producciones/vista-previa", response_model=ProduccionVistaPrevia)
def vista_previa(
    datos: ProduccionCrear,
    ctx: Contexto = Depends(requiere("produccion.crear")),
    db: Session = Depends(obtener_db),
):
    """Insumos que se consumirían por PEPS y costo unitario resultante, sin registrar nada."""
    return service.vista_previa(db, ctx, datos)


@router.get("/producciones/{produccion_id}", response_model=ProduccionSalida)
def ver(
    produccion_id: uuid.UUID,
    ctx: Contexto = Depends(requiere_alguno("produccion.crear", "inventario.ver")),
    db: Session = Depends(obtener_db),
):
    return service.salida(db, service.obtener(db, ctx, produccion_id))


@router.post("/producciones/{produccion_id}/anular", response_model=ProduccionSalida)
def anular(
    produccion_id: uuid.UUID,
    datos: AnulacionEntrada,
    ctx: Contexto = Depends(requiere("produccion.anular")),
    db: Session = Depends(obtener_db),
):
    p = service.anular(db, ctx, produccion_id, datos.motivo)
    salida = service.salida(db, p)
    db.commit()
    return salida
