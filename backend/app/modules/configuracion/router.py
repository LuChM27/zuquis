import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, obtener_contexto, requiere
from app.modules.configuracion import service
from app.modules.configuracion.models import Sede, Unidad
from app.modules.configuracion.schemas import (
    MetodoPagoCrear,
    MetodoPagoEditar,
    MetodoPagoSalida,
    SedeCrear,
    SedeEditar,
    SedeSalida,
    UnidadSalida,
)

router = APIRouter(tags=["Configuración"])
editor = requiere("config.editar")


@router.get("/configuracion")
def leer_configuracion(
    ctx: Contexto = Depends(obtener_contexto), db: Session = Depends(obtener_db)
) -> dict[str, Any]:
    return service.leer(db, ctx.sede_id)


@router.patch("/configuracion")
def actualizar_configuracion(
    cambios: dict[str, Any] = Body(..., examples=[{"dias_alerta_vencimiento": 3}]),
    ctx: Contexto = Depends(editor),
    db: Session = Depends(obtener_db),
) -> dict[str, Any]:
    salida = service.actualizar(db, ctx, cambios)
    db.commit()
    return salida


@router.get("/metodos-pago", response_model=list[MetodoPagoSalida])
def listar_metodos(
    solo_activos: bool = Query(True),
    ctx: Contexto = Depends(obtener_contexto),
    db: Session = Depends(obtener_db),
):
    return service.listar_metodos(db, ctx.sede_id, solo_activos)


@router.post("/metodos-pago", response_model=MetodoPagoSalida, status_code=201)
def crear_metodo(
    datos: MetodoPagoCrear, ctx: Contexto = Depends(editor), db: Session = Depends(obtener_db)
):
    metodo = service.crear_metodo(db, ctx, datos)
    db.commit()
    return metodo


@router.patch("/metodos-pago/{metodo_id}", response_model=MetodoPagoSalida)
def editar_metodo(
    metodo_id: uuid.UUID,
    datos: MetodoPagoEditar,
    ctx: Contexto = Depends(editor),
    db: Session = Depends(obtener_db),
):
    metodo = service.editar_metodo(db, ctx, metodo_id, datos)
    db.commit()
    return metodo


@router.get("/sedes", response_model=list[SedeSalida])
def listar_sedes(_: Contexto = Depends(editor), db: Session = Depends(obtener_db)):
    return list(db.scalars(select(Sede).order_by(Sede.nombre)))


@router.post("/sedes", response_model=SedeSalida, status_code=201)
def crear_sede(
    datos: SedeCrear, ctx: Contexto = Depends(editor), db: Session = Depends(obtener_db)
):
    sede = service.crear_sede(db, ctx, datos)
    db.commit()
    return sede


@router.patch("/sedes/{sede_id}", response_model=SedeSalida)
def editar_sede(
    sede_id: uuid.UUID,
    datos: SedeEditar,
    ctx: Contexto = Depends(editor),
    db: Session = Depends(obtener_db),
):
    sede = service.editar_sede(db, ctx, sede_id, datos)
    db.commit()
    return sede


@router.get("/unidades", response_model=list[UnidadSalida])
def listar_unidades(_: Contexto = Depends(obtener_contexto), db: Session = Depends(obtener_db)):
    return list(db.scalars(select(Unidad).order_by(Unidad.codigo)))
