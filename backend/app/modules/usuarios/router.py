import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.modules.usuarios import service
from app.modules.usuarios.models import Permiso
from app.modules.usuarios.schemas import (
    PermisoSalida,
    RolCrear,
    RolEditar,
    RolSalida,
    UsuarioCrear,
    UsuarioEditar,
    UsuarioSalida,
)

router = APIRouter(tags=["Usuarios y roles"])
admin = requiere("usuarios.gestionar")


@router.get("/permisos", response_model=list[PermisoSalida])
def listar_permisos(
    _: Contexto = Depends(admin), db: Session = Depends(obtener_db)
) -> list[Permiso]:
    return list(db.scalars(select(Permiso).order_by(Permiso.modulo, Permiso.clave)))


@router.get("/roles", response_model=list[RolSalida])
def listar_roles(
    # La sección Negocio también los lista para fijar los topes de descuento.
    _: Contexto = Depends(requiere_alguno("usuarios.gestionar", "config.editar")),
    db: Session = Depends(obtener_db),
):
    return service.listar_roles(db)


@router.post("/roles", response_model=RolSalida, status_code=201)
def crear_rol(datos: RolCrear, ctx: Contexto = Depends(admin), db: Session = Depends(obtener_db)):
    salida = service.crear_rol(db, ctx, datos)
    db.commit()
    return salida


@router.post("/roles/{rol_id}/duplicar", response_model=RolSalida, status_code=201)
def duplicar_rol(
    rol_id: uuid.UUID, ctx: Contexto = Depends(admin), db: Session = Depends(obtener_db)
):
    salida = service.duplicar_rol(db, ctx, rol_id)
    db.commit()
    return salida


@router.patch("/roles/{rol_id}", response_model=RolSalida)
def editar_rol(
    rol_id: uuid.UUID,
    datos: RolEditar,
    ctx: Contexto = Depends(admin),
    db: Session = Depends(obtener_db),
):
    salida = service.editar_rol(db, ctx, rol_id, datos)
    db.commit()
    return salida


@router.delete("/roles/{rol_id}", status_code=204)
def eliminar_rol(
    rol_id: uuid.UUID, ctx: Contexto = Depends(admin), db: Session = Depends(obtener_db)
):
    service.eliminar_rol(db, ctx, rol_id)
    db.commit()
    return Response(status_code=204)


@router.get("/usuarios", response_model=list[UsuarioSalida])
def listar_usuarios(_: Contexto = Depends(admin), db: Session = Depends(obtener_db)):
    return service.listar_usuarios(db)


@router.post("/usuarios", response_model=UsuarioSalida, status_code=201)
def crear_usuario(
    datos: UsuarioCrear, ctx: Contexto = Depends(admin), db: Session = Depends(obtener_db)
):
    salida = service.crear_usuario(db, ctx, datos)
    db.commit()
    return salida


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioSalida)
def editar_usuario(
    usuario_id: uuid.UUID,
    datos: UsuarioEditar,
    ctx: Contexto = Depends(admin),
    db: Session = Depends(obtener_db),
):
    salida = service.editar_usuario(db, ctx, usuario_id, datos)
    db.commit()
    return salida
