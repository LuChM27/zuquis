import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.shared.dinero import Pesos
from app.shared.esquemas import EdicionParcial

Fuente = Literal["caja", "banco", "duenos"]


class CategoriaCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    cuenta_puc: str | None = Field(default=None, max_length=10, pattern=r"^\d{1,10}$")


class CategoriaEditar(EdicionParcial):
    NO_NULOS = ("nombre", "activa")

    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    cuenta_puc: str | None = Field(default=None, max_length=10, pattern=r"^\d{1,10}$")
    activa: bool | None = None


class CategoriaSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    cuenta_puc: str | None
    activa: bool


class GastoCrear(BaseModel):
    fecha: date | None = Field(default=None, description="Por defecto, hoy")
    categoria_id: uuid.UUID
    descripcion: str = Field(min_length=3, max_length=200)
    monto: Pesos = Field(gt=0)
    metodo_pago_id: uuid.UUID
    fuente: Fuente = Field(description="caja: sale del arqueo; banco o dueños: no")
    proveedor_id: uuid.UUID | None = None
    soporte_url: str | None = Field(default=None, max_length=300)


class AnulacionEntrada(BaseModel):
    motivo: str = Field(min_length=3, max_length=200)


class GastoSalida(BaseModel):
    id: uuid.UUID
    fecha: date
    categoria_id: uuid.UUID
    categoria: str | None = None
    cuenta_puc: str | None = None
    descripcion: str
    monto: int
    metodo_pago_id: uuid.UUID
    metodo: str | None = None
    fuente: str
    caja_sesion_id: uuid.UUID | None
    proveedor_id: uuid.UUID | None
    encargo_id: uuid.UUID | None
    encargo_numero: int | None = None
    soporte_url: str | None
    estado: str
    usuario: str | None = None
    motivo_anulacion: str | None
    creado_en: datetime
