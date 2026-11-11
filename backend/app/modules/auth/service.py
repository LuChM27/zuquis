"""Inicio de sesión, renovación rotada y cierre de sesión (sección 11)."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import obtener_config
from app.core.seguridad import (
    HASH_FICTICIO,
    crear_access_token,
    hash_refresh,
    nuevo_refresh_token,
    verificar_clave,
)
from app.modules.auditoria.service import auditar
from app.modules.auth.models import SesionRefresh, Usuario
from app.modules.configuracion.models import Sede
from app.modules.usuarios.models import Rol, UsuarioRol
from app.shared.errores import Conflicto, ErrorNegocio, NoAutenticado
from app.shared.fechas import ahora

# Dos pestañas pueden renovar a la vez con el mismo token. Dentro de esta ventana no se
# trata como robo: se responde 401 sin revocar toda la sesión.
GRACIA_ROTACION = timedelta(seconds=10)


@dataclass
class Sesion:
    usuario: Usuario
    sede: Sede
    access_token: str
    expira_en: datetime
    refresh_token: str


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def sedes_del_usuario(db: Session, usuario_id: uuid.UUID) -> list[Sede]:
    """Sedes donde el usuario tiene al menos un rol activo (las mismas que dan permisos)."""
    consulta = (
        select(Sede)
        .join(UsuarioRol, UsuarioRol.sede_id == Sede.id)
        .join(Rol, Rol.id == UsuarioRol.rol_id)
        .where(UsuarioRol.usuario_id == usuario_id, Sede.activa, Rol.activo)
        .distinct()
        .order_by(Sede.nombre)
    )
    return list(db.scalars(consulta))


def _abrir_sesion(
    db: Session, usuario: Usuario, sede: Sede, familia_id: uuid.UUID
) -> tuple[SesionRefresh, str]:
    token, token_hash = nuevo_refresh_token()
    sesion = SesionRefresh(
        usuario_id=usuario.id,
        sede_id=sede.id,
        familia_id=familia_id,
        token_hash=token_hash,
        creado_en=ahora(),
        expira_en=ahora() + timedelta(days=obtener_config().refresh_dias),
    )
    db.add(sesion)
    db.flush()
    return sesion, token


def iniciar_sesion(
    db: Session, email: str, clave: str, sede_id: uuid.UUID | None, ip: str | None
) -> Sesion:
    """Valida credenciales. Los intentos fallidos se guardan aunque la petición falle:
    el router confirma la transacción también cuando este servicio lanza error."""
    cfg = obtener_config()
    usuario = db.scalar(
        select(Usuario)
        .where(func.lower(Usuario.email) == normalizar_email(email))
        .with_for_update()
    )

    if usuario is None:
        verificar_clave(HASH_FICTICIO, clave)  # mismo tiempo de respuesta
        auditar(
            db, None, "login_fallido", "usuarios", despues={"email": normalizar_email(email)}, ip=ip
        )
        raise NoAutenticado("Usuario o contraseña incorrectos.", "CREDENCIALES_INVALIDAS")

    if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora():
        # Con contraseña equivocada se responde igual que a un correo inexistente: el bloqueo
        # no debe revelar qué correos existen. Tampoco se extiende el bloqueo, para que nadie
        # pueda mantener bloqueada la cuenta de otra persona.
        if not verificar_clave(usuario.password_hash, clave):
            auditar(db, None, "login_fallido", "usuarios", usuario.id, usuario_id=usuario.id, ip=ip)
            raise NoAutenticado("Usuario o contraseña incorrectos.", "CREDENCIALES_INVALIDAS")
        raise ErrorNegocio(
            "USUARIO_BLOQUEADO",
            "Demasiados intentos fallidos. Intenta de nuevo más tarde.",
            {"hasta": usuario.bloqueado_hasta.isoformat()},
            status=423,
        )

    if not verificar_clave(usuario.password_hash, clave) or not usuario.activo:
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= cfg.login_max_intentos:
            usuario.bloqueado_hasta = ahora() + timedelta(minutes=cfg.login_bloqueo_minutos)
            usuario.intentos_fallidos = 0
        auditar(db, None, "login_fallido", "usuarios", usuario.id, usuario_id=usuario.id, ip=ip)
        raise NoAutenticado("Usuario o contraseña incorrectos.", "CREDENCIALES_INVALIDAS")

    sedes = sedes_del_usuario(db, usuario.id)
    if not sedes:
        raise NoAutenticado(
            "Tu usuario no tiene roles asignados. Habla con el administrador.", "SIN_ROLES"
        )
    if sede_id is not None:
        sede = next((s for s in sedes if s.id == sede_id), None)
        if sede is None:
            raise NoAutenticado("No tienes acceso a esa sede.", "SEDE_NO_PERMITIDA")
    elif len(sedes) == 1:
        sede = sedes[0]
    else:
        raise Conflicto(
            "SEDE_REQUERIDA",
            "Elige la sede.",
            {"sedes": [{"id": str(s.id), "nombre": s.nombre} for s in sedes]},
        )

    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.ultimo_acceso = ahora()
    _, refresh = _abrir_sesion(db, usuario, sede, uuid.uuid4())
    access, expira = crear_access_token(usuario.id, sede.id)
    auditar(
        db, None, "login", "usuarios", usuario.id, usuario_id=usuario.id, sede_id=sede.id, ip=ip
    )
    return Sesion(usuario, sede, access, expira, refresh)


def renovar(db: Session, refresh_token: str | None) -> Sesion:
    if not refresh_token:
        raise NoAutenticado("La sesión expiró.", "REFRESH_AUSENTE")
    actual = db.scalar(
        select(SesionRefresh)
        .where(SesionRefresh.token_hash == hash_refresh(refresh_token))
        .with_for_update()
    )
    if actual is None:
        raise NoAutenticado("La sesión expiró.", "REFRESH_INVALIDO")

    if actual.revocado_en is not None:
        if actual.reemplazado_por and ahora() - actual.revocado_en < GRACIA_ROTACION:
            raise NoAutenticado("La sesión se renovó en otra pestaña.", "REFRESH_ROTADO")
        # Reutilización de un token ya usado: posible robo. Se cierra toda la sesión.
        revocar_familia(db, actual.familia_id)
        raise NoAutenticado("La sesión fue cerrada por seguridad.", "REFRESH_REUTILIZADO")

    if actual.expira_en <= ahora():
        raise NoAutenticado("La sesión expiró.", "REFRESH_EXPIRADO")

    usuario = db.get(Usuario, actual.usuario_id)
    sede = db.get(Sede, actual.sede_id)
    if usuario is None or not usuario.activo or sede is None or not sede.activa:
        revocar_familia(db, actual.familia_id)
        raise NoAutenticado("El usuario no está activo.", "USUARIO_INACTIVO")
    if sede.id not in {s.id for s in sedes_del_usuario(db, usuario.id)}:
        revocar_familia(db, actual.familia_id)
        raise NoAutenticado(
            "Tu usuario ya no tiene roles activos en esta sede. Habla con el administrador.",
            "SIN_ROLES",
        )

    nueva, refresh = _abrir_sesion(db, usuario, sede, actual.familia_id)
    actual.revocado_en = ahora()
    actual.reemplazado_por = nueva.id
    access, expira = crear_access_token(usuario.id, sede.id)
    return Sesion(usuario, sede, access, expira, refresh)


def revocar_familia(db: Session, familia_id: uuid.UUID) -> None:
    db.execute(
        update(SesionRefresh)
        .where(SesionRefresh.familia_id == familia_id, SesionRefresh.revocado_en.is_(None))
        .values(revocado_en=ahora())
    )


def cerrar_sesion(db: Session, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    actual = db.scalar(
        select(SesionRefresh).where(SesionRefresh.token_hash == hash_refresh(refresh_token))
    )
    if actual is not None:
        revocar_familia(db, actual.familia_id)
