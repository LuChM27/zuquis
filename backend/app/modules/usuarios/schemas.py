import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.esquemas import EdicionParcial


class PermisoSalida(BaseModel):
    clave: str
    descripcion: str
    modulo: str


class RolSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    descripcion: str | None
    es_base: bool
    activo: bool
    permisos: list[str]
    usuarios: int


class RolCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    descripcion: str | None = Field(default=None, max_length=200)
    permisos: list[str] = Field(default_factory=list)


class RolEditar(EdicionParcial):
    NO_NULOS = ("nombre", "activo", "permisos")

    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    descripcion: str | None = Field(default=None, max_length=200)
    activo: bool | None = None
    permisos: list[str] | None = None


class AsignacionRol(BaseModel):
    rol_id: uuid.UUID
    sede_id: uuid.UUID


class AsignacionSalida(AsignacionRol):
    rol_nombre: str


class UsuarioSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    email: str
    activo: bool
    bloqueado: bool
    ultimo_acceso: datetime | None
    roles: list[AsignacionSalida]


class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=200)
    roles: list[AsignacionRol] = Field(min_length=1)


class UsuarioEditar(EdicionParcial):
    NO_NULOS = ("nombre", "email", "password", "activo", "roles")

    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(
        default=None, min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )
    password: str | None = Field(default=None, min_length=8, max_length=200)
    activo: bool | None = None
    desbloquear: bool = False
    roles: list[AsignacionRol] | None = Field(default=None, min_length=1)
