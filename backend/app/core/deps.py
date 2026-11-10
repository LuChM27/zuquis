"""Dependencias de autenticación y autorización.

Cada endpoint declara el permiso que exige con ``Depends(requiere("ventas.anular"))``. El
backend lo valida siempre; ocultar botones en el frontend no reemplaza esta validación.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.seguridad import leer_access_token
from app.shared.errores import NoAutenticado, SinPermiso

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Contexto:
    """Quién hace la petición y en qué sede."""

    usuario_id: uuid.UUID
    sede_id: uuid.UUID
    permisos: frozenset[str] = field(default_factory=frozenset)
    ip: str | None = None

    def puede(self, permiso: str) -> bool:
        return permiso in self.permisos


def permisos_en_sede(db: Session, usuario_id: uuid.UUID, sede_id: uuid.UUID) -> frozenset[str]:
    """Unión de los permisos de todos los roles activos del usuario en la sede."""
    from app.modules.usuarios.models import Permiso, Rol, UsuarioRol, rol_permisos

    consulta = (
        select(Permiso.clave)
        .join(rol_permisos, rol_permisos.c.permiso_id == Permiso.id)
        .join(Rol, Rol.id == rol_permisos.c.rol_id)
        .join(UsuarioRol, UsuarioRol.rol_id == Rol.id)
        .where(UsuarioRol.usuario_id == usuario_id, UsuarioRol.sede_id == sede_id, Rol.activo)
        .distinct()
    )
    return frozenset(db.scalars(consulta))


def ip_cliente(request: Request) -> str | None:
    return request.client.host if request.client else None


def obtener_contexto(
    request: Request,
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(obtener_db),
) -> Contexto:
    from app.modules.auth.models import Usuario

    if credenciales is None or credenciales.scheme.lower() != "bearer":
        raise NoAutenticado()
    try:
        carga = leer_access_token(credenciales.credentials)
        usuario_id = uuid.UUID(carga["sub"])
        sede_id = uuid.UUID(carga["sede"])
    except jwt.ExpiredSignatureError as exc:
        raise NoAutenticado("La sesión expiró.", "TOKEN_EXPIRADO") from exc
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise NoAutenticado("Token inválido.", "TOKEN_INVALIDO") from exc

    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise NoAutenticado("El usuario no está activo.", "USUARIO_INACTIVO")

    ctx = Contexto(
        usuario_id=usuario_id,
        sede_id=sede_id,
        permisos=permisos_en_sede(db, usuario_id, sede_id),
        ip=ip_cliente(request),
    )
    if not ctx.permisos:
        raise NoAutenticado("No tienes roles en esta sede.", "SIN_ROLES_EN_SEDE")
    # creado_por y la auditoría toman el usuario de aquí (ver app.core.modelo).
    db.info["usuario_id"] = usuario_id
    db.info["sede_id"] = sede_id
    return ctx


def requiere(*permisos: str) -> Callable[..., Contexto]:
    """Exige todos los permisos indicados."""
    from app.core.permisos import CLAVES

    desconocidos = set(permisos) - CLAVES
    assert not desconocidos, f"Permisos fuera del catálogo: {desconocidos}"

    def dependencia(ctx: Contexto = Depends(obtener_contexto)) -> Contexto:
        for permiso in permisos:
            if not ctx.puede(permiso):
                raise SinPermiso(permiso)
        return ctx

    return dependencia


def requiere_alguno(*permisos: str) -> Callable[..., Contexto]:
    """Exige al menos uno de los permisos indicados."""

    def dependencia(ctx: Contexto = Depends(obtener_contexto)) -> Contexto:
        if not any(ctx.puede(p) for p in permisos):
            raise SinPermiso(" | ".join(permisos))
        return ctx

    return dependencia
