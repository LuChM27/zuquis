"""Registro de todos los modelos, para Alembic y las pruebas de guardia."""

from app.core.idempotencia_models import Idempotencia
from app.core.modelo import Base
from app.modules.auditoria.models import Auditoria
from app.modules.auth.models import SesionRefresh, Usuario
from app.modules.configuracion.models import Configuracion, MetodoPago, Sede, Unidad
from app.modules.usuarios.models import Permiso, Rol, UsuarioRol, rol_permisos

__all__ = [
    "Auditoria",
    "Base",
    "Configuracion",
    "Idempotencia",
    "MetodoPago",
    "Permiso",
    "Rol",
    "Sede",
    "SesionRefresh",
    "Unidad",
    "Usuario",
    "UsuarioRol",
    "rol_permisos",
]
