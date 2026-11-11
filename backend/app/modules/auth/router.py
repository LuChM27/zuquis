from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import obtener_config
from app.core.db import obtener_db
from app.core.deps import Contexto, ip_cliente, obtener_contexto
from app.core.limite import limitar
from app.modules.auth import service
from app.modules.auth.models import Usuario
from app.modules.auth.schemas import (
    LoginEntrada,
    SedeResumen,
    TokenSalida,
    UsuarioResumen,
    YoSalida,
)
from app.modules.configuracion.models import Sede
from app.modules.usuarios.models import Rol, UsuarioRol
from app.shared.errores import ErrorNegocio

router = APIRouter(prefix="/auth", tags=["Autenticación"])

COOKIE_REFRESH = "zuquis_refresh"
RUTA_COOKIE = "/api/v1/auth"


def _poner_cookie(respuesta: Response, token: str) -> None:
    cfg = obtener_config()
    respuesta.set_cookie(
        COOKIE_REFRESH,
        token,
        max_age=cfg.refresh_dias * 24 * 3600,
        path=RUTA_COOKIE,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite="strict",
    )


def _quitar_cookie(respuesta: Response) -> None:
    cfg = obtener_config()
    respuesta.delete_cookie(
        COOKIE_REFRESH, path=RUTA_COOKIE, httponly=True, secure=cfg.cookie_secure, samesite="strict"
    )


def _salida(sesion: service.Sesion) -> TokenSalida:
    return TokenSalida(
        access_token=sesion.access_token,
        expira_en=sesion.expira_en,
        usuario=UsuarioResumen.model_validate(sesion.usuario, from_attributes=True),
        sede=SedeResumen.model_validate(sesion.sede, from_attributes=True),
    )


@router.post(
    "/login",
    response_model=TokenSalida,
    dependencies=[Depends(limitar("login", lambda: obtener_config().login_limite_por_minuto))],
)
def login(
    datos: LoginEntrada, request: Request, response: Response, db: Session = Depends(obtener_db)
) -> TokenSalida:
    try:
        sesion = service.iniciar_sesion(
            db, datos.email, datos.password, datos.sede_id, ip_cliente(request)
        )
    except ErrorNegocio:
        db.commit()  # guarda el intento fallido y su auditoría
        raise
    db.commit()
    _poner_cookie(response, sesion.refresh_token)
    return _salida(sesion)


@router.post(
    "/refresh",
    response_model=TokenSalida,
    dependencies=[Depends(limitar("refresh", lambda: 60))],
)
def refresh(
    response: Response,
    db: Session = Depends(obtener_db),
    zuquis_refresh: str | None = Cookie(default=None),
) -> TokenSalida:
    try:
        sesion = service.renovar(db, zuquis_refresh)
    except ErrorNegocio:
        db.commit()  # guarda la revocación si hubo reutilización
        raise
    db.commit()
    _poner_cookie(response, sesion.refresh_token)
    return _salida(sesion)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Session = Depends(obtener_db),
    zuquis_refresh: str | None = Cookie(default=None),
) -> Response:
    service.cerrar_sesion(db, zuquis_refresh)
    db.commit()
    respuesta = Response(status_code=204)
    _quitar_cookie(respuesta)
    return respuesta


@router.get("/me", response_model=YoSalida)
def yo(ctx: Contexto = Depends(obtener_contexto), db: Session = Depends(obtener_db)) -> YoSalida:
    usuario = db.get(Usuario, ctx.usuario_id)
    sede = db.get(Sede, ctx.sede_id)
    nombres = db.scalars(
        select(Rol.nombre)
        .join(UsuarioRol, UsuarioRol.rol_id == Rol.id)
        .where(
            UsuarioRol.usuario_id == ctx.usuario_id, UsuarioRol.sede_id == ctx.sede_id, Rol.activo
        )
        .order_by(Rol.nombre)
    ).all()
    return YoSalida(
        usuario=UsuarioResumen.model_validate(usuario, from_attributes=True),
        sede=SedeResumen.model_validate(sede, from_attributes=True),
        sedes=[
            SedeResumen.model_validate(s, from_attributes=True)
            for s in service.sedes_del_usuario(db, ctx.usuario_id)
        ],
        roles=list(nombres),
        permisos=sorted(ctx.permisos),
    )
