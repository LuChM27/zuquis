import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClienteCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=200)
    notas: str | None = Field(default=None, max_length=500)
    autoriza_datos: bool = Field(
        default=False, description="Ley 1581: autorizó el tratamiento de sus datos"
    )
    permitir_telefono_repetido: bool = Field(
        default=False, description="Crear aunque otro cliente ya tenga ese teléfono"
    )


class ClienteEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=200)
    notas: str | None = Field(default=None, max_length=500)
    autoriza_datos: bool | None = None
    activo: bool | None = None
    permitir_telefono_repetido: bool = False


class ClienteSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    telefono: str | None
    direccion: str | None
    notas: str | None
    autoriza_datos: bool
    autorizo_en: datetime | None
    activo: bool


class VentaHistorial(BaseModel):
    id: uuid.UUID
    numero: int
    fecha: datetime
    total: int
    estado: str
    tipo_servicio: str


class EncargoHistorial(BaseModel):
    id: uuid.UUID
    numero: int
    descripcion: str
    fecha_entrega: datetime
    total: int
    estado: str


class DomicilioHistorial(BaseModel):
    id: uuid.UUID
    fecha: datetime
    direccion: str
    valor: int
    estado: str


class Historial(BaseModel):
    cliente: ClienteSalida
    ventas: list[VentaHistorial]
    encargos: list[EncargoHistorial]
    domicilios: list[DomicilioHistorial]
    total_comprado: int = Field(description="Σ ventas pagadas del cliente")
