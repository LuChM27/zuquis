import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.modules.inventario import service
from app.modules.inventario.models import Insumo, Presentacion
from app.modules.inventario.schemas import (
    InsumoCrear,
    InsumoEditar,
    InsumoSalida,
    PresentacionCrear,
    PresentacionEditar,
    PresentacionSalida,
)

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
