"""Tope de descuento por rol y autorización de un tercero (#30, RF-11, RN-16, RN-17).

Cada descuento (de un ítem o de la venta) se compara con el tope del rol de quien vende. Si lo
supera, un usuario con `descuentos.autorizar` lo aprueba con su credencial en la misma petición.
Quien tiene `descuentos.autorizar` no necesita autorización; quien no tiene
`descuentos.aplicar` necesita autorización para cualquier descuento.
"""

import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import obtener_config
from app.core.deps import Contexto, permisos_en_sede
from app.core.seguridad import verificar_clave
from app.modules.auditoria.service import auditar
from app.modules.auth.models import Usuario
from app.modules.auth.service import normalizar_email
from app.modules.configuracion import service as configuracion
from app.modules.usuarios.models import UsuarioRol
from app.shared.errores import ErrorNegocio
from app.shared.fechas import ahora


class AutorizacionInvalida(ErrorNegocio):
    """La credencial del autorizador no sirve. Lleva el usuario para contar el intento fallido
    fuera de la transacción de la venta, que se revierte."""

    status = 403

    def __init__(self, usuario_id: uuid.UUID | None = None):
        super().__init__(
            "AUTORIZACION_INVALIDA",
            "La autorización no es válida: revisa el usuario y la contraseña de quien autoriza, "
            "y que tenga permiso para autorizar descuentos.",
        )
        self.usuario_id = usuario_id


def tope_del_usuario(db: Session, ctx: Contexto) -> Decimal | None:
    """Porcentaje máximo sin autorización; None = sin límite."""
    if "descuentos.autorizar" in ctx.permisos:
        return None
    if "descuentos.aplicar" not in ctx.permisos:
        return Decimal(0)
    topes = configuracion.valor(db, ctx.sede_id, "tope_descuento_por_rol")
    roles = db.scalars(
        select(UsuarioRol.rol_id).where(
            UsuarioRol.usuario_id == ctx.usuario_id, UsuarioRol.sede_id == ctx.sede_id
        )
    ).all()
    return max((Decimal(topes.get(r, 0)) for r in roles), default=Decimal(0))


def supera_tope(monto: int, base: int, tope: Decimal | None) -> bool:
    """monto / base > tope %, comparado sin divisiones (exacto)."""
    return tope is not None and monto > 0 and Decimal(monto) * 100 > Decimal(base) * tope


def verificar_autorizador(db: Session, ctx: Contexto, email: str, clave: str) -> Usuario:
    """Credencial + permiso `descuentos.autorizar` en la sede. Respeta el bloqueo por intentos."""
    usuario = db.scalar(select(Usuario).where(func.lower(Usuario.email) == normalizar_email(email)))
    if usuario is None or not usuario.activo:
        raise AutorizacionInvalida()
    bloqueado = usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora()
    if bloqueado or not verificar_clave(usuario.password_hash, clave):
        raise AutorizacionInvalida(None if bloqueado else usuario.id)
    if "descuentos.autorizar" not in permisos_en_sede(db, usuario.id, ctx.sede_id):
        raise AutorizacionInvalida()
    return usuario


def verificar_autorizador_pin(
    db: Session, ctx: Contexto, usuario_id: uuid.UUID, pin: str
) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo or usuario.pin_hash is None:
        raise AutorizacionInvalida()
    bloqueado = usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora()
    if bloqueado or not verificar_clave(usuario.pin_hash, pin):
        raise AutorizacionInvalida(None if bloqueado else usuario.id)
    if "descuentos.autorizar" not in permisos_en_sede(db, usuario.id, ctx.sede_id):
        raise AutorizacionInvalida()
    return usuario


def contar_intento_fallido(db: Session, usuario_id: uuid.UUID) -> None:
    """Igual que en el login: tras N intentos, la cuenta se bloquea un tiempo."""
    cfg = obtener_config()
    usuario = db.get(Usuario, usuario_id, with_for_update=True)
    if usuario is None:
        return
    usuario.intentos_fallidos += 1
    if usuario.intentos_fallidos >= cfg.login_max_intentos:
        usuario.bloqueado_hasta = ahora() + timedelta(minutes=cfg.login_bloqueo_minutos)
        usuario.intentos_fallidos = 0
    auditar(db, None, "autorizacion_fallida", "usuarios", usuario.id, usuario_id=usuario.id)


def auditar_autorizacion(
    db: Session, ctx: Contexto, autorizador: Usuario, venta_id: uuid.UUID, descuento_total: int
) -> None:
    auditar(
        db,
        ctx,
        "autorizar_descuento",
        "ventas",
        venta_id,
        despues={"descuento_total": descuento_total, "vendedor": str(ctx.usuario_id)},
        usuario_id=autorizador.id,
    )
