import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LoginEntrada(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)
    sede_id: uuid.UUID | None = None


class SedeResumen(BaseModel):
    id: uuid.UUID
    nombre: str


class UsuarioResumen(BaseModel):
    id: uuid.UUID
    nombre: str
    email: str


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expira_en: datetime
    usuario: UsuarioResumen
    sede: SedeResumen


class YoSalida(BaseModel):
    usuario: UsuarioResumen
    sede: SedeResumen
    sedes: list[SedeResumen]
    roles: list[str]
    permisos: list[str]
