"""Usuarios y roles configurables (sección 2, RF-45)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.core.permisos import CLAVES
from app.core.seguridad import hashear_clave
from app.modules.auditoria.service import auditar, instantanea
from app.modules.auth.models import SesionRefresh, Usuario
from app.modules.auth.service import normalizar_email, revocar_familia
from app.modules.configuracion.models import Sede
from app.modules.usuarios.models import Permiso, Rol, UsuarioRol, rol_permisos
from app.modules.usuarios.schemas import (
    AsignacionRol,
    AsignacionSalida,
    RolCrear,
    RolEditar,
    RolSalida,
    UsuarioCrear,
    UsuarioEditar,
    UsuarioSalida,
)
from app.shared.errores import Conflicto, ErrorNegocio, NoEncontrado
from app.shared.fechas import ahora

PERMISO_ADMIN = "usuarios.gestionar"

# --- Roles ----------------------------------------------------------------------------------


def _usuarios_por_rol(db: Session) -> dict[uuid.UUID, int]:
    filas = db.execute(
        select(UsuarioRol.rol_id, func.count(func.distinct(UsuarioRol.usuario_id))).group_by(
            UsuarioRol.rol_id
        )
    )
    return {rol_id: n for rol_id, n in filas}


def rol_salida(rol: Rol, usuarios: int) -> RolSalida:
    return RolSalida(
        id=rol.id,
        nombre=rol.nombre,
        descripcion=rol.descripcion,
        es_base=rol.es_base,
        activo=rol.activo,
        permisos=sorted(p.clave for p in rol.permisos),
        usuarios=usuarios,
    )


def listar_roles(db: Session) -> list[RolSalida]:
    conteo = _usuarios_por_rol(db)
    roles = db.scalars(select(Rol).order_by(Rol.es_base.desc(), Rol.nombre))
    return [rol_salida(r, conteo.get(r.id, 0)) for r in roles]


def _permisos(db: Session, claves: list[str]) -> list[Permiso]:
    desconocidas = set(claves) - CLAVES
    if desconocidas:
        raise ErrorNegocio(
            "PERMISO_DESCONOCIDO",
            "Hay permisos que no existen.",
            {"permisos": sorted(desconocidas)},
            status=422,
        )
    if not claves:
        return []
    return list(db.scalars(select(Permiso).where(Permiso.clave.in_(set(claves)))))


def _nombre_libre(db: Session, nombre: str, excepto: uuid.UUID | None = None) -> None:
    consulta = select(Rol.id).where(func.lower(Rol.nombre) == nombre.strip().lower())
    if excepto:
        consulta = consulta.where(Rol.id != excepto)
    if db.scalar(consulta):
        raise Conflicto("ROL_DUPLICADO", "Ya existe un rol con ese nombre.")


def _obtener_rol(db: Session, rol_id: uuid.UUID) -> Rol:
    rol = db.get(Rol, rol_id)
    if rol is None:
        raise NoEncontrado("el rol", rol_id)
    return rol


_CAMPOS_ROL = ["nombre", "descripcion", "activo"]


def _foto_rol(rol: Rol) -> dict:
    return instantanea(rol, _CAMPOS_ROL) | {"permisos": sorted(p.clave for p in rol.permisos)}


def crear_rol(db: Session, ctx: Contexto, datos: RolCrear) -> RolSalida:
    _nombre_libre(db, datos.nombre)
    rol = Rol(
        nombre=datos.nombre.strip(),
        descripcion=datos.descripcion,
        permisos=_permisos(db, datos.permisos),
    )
    db.add(rol)
    db.flush()
    auditar(db, ctx, "crear", "roles", rol.id, despues=_foto_rol(rol))
    return rol_salida(rol, 0)


def duplicar_rol(db: Session, ctx: Contexto, rol_id: uuid.UUID) -> RolSalida:
    origen = _obtener_rol(db, rol_id)
    nombre = f"{origen.nombre} (copia)"
    n = 2
    while db.scalar(select(Rol.id).where(Rol.nombre == nombre)):
        nombre = f"{origen.nombre} (copia {n})"
        n += 1
    return crear_rol(
        db,
        ctx,
        RolCrear(
            nombre=nombre,
            descripcion=origen.descripcion,
            permisos=[p.clave for p in origen.permisos],
        ),
    )


def editar_rol(db: Session, ctx: Contexto, rol_id: uuid.UUID, datos: RolEditar) -> RolSalida:
    rol = _obtener_rol(db, rol_id)
    antes = _foto_rol(rol)
    usuarios = _usuarios_por_rol(db).get(rol.id, 0)

    if datos.nombre is not None:
        _nombre_libre(db, datos.nombre, excepto=rol.id)
        rol.nombre = datos.nombre.strip()
    if datos.descripcion is not None:
        rol.descripcion = datos.descripcion
    if datos.activo is False and rol.activo and rol.es_base and usuarios:
        raise Conflicto(
            "ROL_BASE_CON_USUARIOS",
            "No se puede desactivar un rol base mientras tenga usuarios asignados.",
            {"usuarios": usuarios},
        )
    if datos.activo is not None:
        rol.activo = datos.activo
    if datos.permisos is not None:
        rol.permisos = _permisos(db, datos.permisos)
    db.flush()
    verificar_queda_administrador(db)
    auditar(db, ctx, "editar", "roles", rol.id, antes=antes, despues=_foto_rol(rol))
    return rol_salida(rol, usuarios)


def eliminar_rol(db: Session, ctx: Contexto, rol_id: uuid.UUID) -> None:
    rol = _obtener_rol(db, rol_id)
    usuarios = _usuarios_por_rol(db).get(rol.id, 0)
    if usuarios:
        raise Conflicto(
            "ROL_CON_USUARIOS",
            "No se puede eliminar un rol con usuarios asignados.",
            {"usuarios": usuarios},
        )
    antes = _foto_rol(rol)
    db.delete(rol)
    db.flush()
    auditar(db, ctx, "eliminar", "roles", rol_id, antes=antes)


def verificar_queda_administrador(db: Session) -> None:
    """Evita quedarse sin nadie que pueda administrar usuarios y roles."""
    hay = db.scalar(
        select(func.count())
        .select_from(UsuarioRol)
        .join(Usuario, Usuario.id == UsuarioRol.usuario_id)
        .join(Rol, Rol.id == UsuarioRol.rol_id)
        .join(rol_permisos, rol_permisos.c.rol_id == Rol.id)
        .join(Permiso, Permiso.id == rol_permisos.c.permiso_id)
        .where(Usuario.activo, Rol.activo, Permiso.clave == PERMISO_ADMIN)
    )
    if not hay:
        raise Conflicto(
            "SIN_ADMINISTRADOR",
            "El cambio dejaría el sistema sin ningún usuario que administre usuarios y roles.",
        )


# --- Usuarios -------------------------------------------------------------------------------


def usuario_salida(db: Session, usuario: Usuario) -> UsuarioSalida:
    filas = db.execute(
        select(UsuarioRol.rol_id, UsuarioRol.sede_id, Rol.nombre)
        .join(Rol, Rol.id == UsuarioRol.rol_id)
        .where(UsuarioRol.usuario_id == usuario.id)
        .order_by(Rol.nombre)
    )
    return UsuarioSalida(
        id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        activo=usuario.activo,
        bloqueado=bool(usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora()),
        ultimo_acceso=usuario.ultimo_acceso,
        roles=[AsignacionSalida(rol_id=r, sede_id=s, rol_nombre=n) for r, s, n in filas],
    )


def listar_usuarios(db: Session) -> list[UsuarioSalida]:
    return [usuario_salida(db, u) for u in db.scalars(select(Usuario).order_by(Usuario.nombre))]


def _email_libre(db: Session, email: str, excepto: uuid.UUID | None = None) -> str:
    email = normalizar_email(email)
    consulta = select(Usuario.id).where(func.lower(Usuario.email) == email)
    if excepto:
        consulta = consulta.where(Usuario.id != excepto)
    if db.scalar(consulta):
        raise Conflicto("EMAIL_DUPLICADO", "Ya existe un usuario con ese correo.")
    return email


def _asignar_roles(db: Session, usuario_id: uuid.UUID, asignaciones: list[AsignacionRol]) -> None:
    unicas = {(a.rol_id, a.sede_id) for a in asignaciones}
    for rol_id, sede_id in unicas:
        if db.get(Rol, rol_id) is None:
            raise NoEncontrado("el rol", rol_id)
        if db.get(Sede, sede_id) is None:
            raise NoEncontrado("la sede", sede_id)
    for existente in db.scalars(select(UsuarioRol).where(UsuarioRol.usuario_id == usuario_id)):
        db.delete(existente)
    db.flush()
    for rol_id, sede_id in sorted(unicas):
        db.add(UsuarioRol(usuario_id=usuario_id, rol_id=rol_id, sede_id=sede_id))
    db.flush()


def _foto_usuario(db: Session, usuario: Usuario) -> dict:
    salida = usuario_salida(db, usuario)
    return {
        "nombre": salida.nombre,
        "email": salida.email,
        "activo": salida.activo,
        "roles": [{"rol": r.rol_nombre, "sede_id": str(r.sede_id)} for r in salida.roles],
    }


def crear_usuario(db: Session, ctx: Contexto, datos: UsuarioCrear) -> UsuarioSalida:
    usuario = Usuario(
        nombre=datos.nombre.strip(),
        email=_email_libre(db, datos.email),
        password_hash=hashear_clave(datos.password),
    )
    db.add(usuario)
    db.flush()
    _asignar_roles(db, usuario.id, datos.roles)
    auditar(db, ctx, "crear", "usuarios", usuario.id, despues=_foto_usuario(db, usuario))
    return usuario_salida(db, usuario)


def editar_usuario(
    db: Session, ctx: Contexto, usuario_id: uuid.UUID, datos: UsuarioEditar
) -> UsuarioSalida:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise NoEncontrado("el usuario", usuario_id)
    antes = _foto_usuario(db, usuario)

    if datos.nombre is not None:
        usuario.nombre = datos.nombre.strip()
    if datos.email is not None:
        usuario.email = _email_libre(db, datos.email, excepto=usuario.id)
    if datos.desbloquear:
        usuario.bloqueado_hasta = None
        usuario.intentos_fallidos = 0
    if datos.roles is not None:
        _asignar_roles(db, usuario.id, datos.roles)

    cerrar_sesiones = False
    if datos.password is not None:
        usuario.password_hash = hashear_clave(datos.password)
        cerrar_sesiones = True
    if datos.activo is not None:
        usuario.activo = datos.activo
        cerrar_sesiones = cerrar_sesiones or not datos.activo
    if cerrar_sesiones:
        familias = db.scalars(
            select(SesionRefresh.familia_id)
            .where(SesionRefresh.usuario_id == usuario.id)
            .distinct()
        )
        for familia in familias:
            revocar_familia(db, familia)

    db.flush()
    verificar_queda_administrador(db)
    despues = _foto_usuario(db, usuario)
    if datos.password is not None:
        despues["password"] = "cambiada"  # noqa: S105 (solo marca el cambio en la auditoría)
    auditar(db, ctx, "editar", "usuarios", usuario.id, antes=antes, despues=despues)
    return usuario_salida(db, usuario)
