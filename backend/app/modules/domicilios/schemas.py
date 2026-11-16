import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.shared.dinero import Pesos

EstadoDomicilio = Literal["pendiente", "en_camino", "entregado"]


class DomiciliarioCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    telefono: str | None = Field(default=None, max_length=30)


class DomiciliarioEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    telefono: str | None = Field(default=None, max_length=30)
    activo: bool | None = None


class DomiciliarioSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    telefono: str | None
    activo: bool


class DomicilioEntrada(BaseModel):
    """Datos de la entrega al vender a domicilio (RF-13). El valor va en la venta."""

    domiciliario_id: uuid.UUID
    direccion: str = Field(min_length=3, max_length=200)
    telefono: str | None = Field(default=None, max_length=30)
    contacto: str | None = Field(
        default=None, max_length=120, description="Nombre de quien recibe, si no es un cliente"
    )


class DomicilioCambio(BaseModel):
    estado: EstadoDomicilio | None = None
    domiciliario_id: uuid.UUID | None = None


class DomicilioSalida(BaseModel):
    id: uuid.UUID
    fecha: datetime
    venta_id: uuid.UUID
    venta_numero: int
    encargo_id: uuid.UUID | None
    encargo_numero: int | None
    cliente_id: uuid.UUID | None
    cliente: str | None
    direccion: str
    telefono: str | None
    domiciliario_id: uuid.UUID
    domiciliario: str
    valor: int
    total_venta: int
    estado: str
    liquidado_en: datetime | None


class LiquidacionDomiciliario(BaseModel):
    """Lo que la caja abierta le debe (o ya le entregó) a un domiciliario."""

    domiciliario_id: uuid.UUID
    domiciliario: str
    domicilios: int
    cobrado: int
    entregado: int
    pendiente: int


class LiquidacionTurno(BaseModel):
    domicilios: int
    cobrado: int
    entregado: int
    pendiente: int
    domiciliarios: list[LiquidacionDomiciliario]


class LiquidarEntrada(BaseModel):
    domiciliario_id: uuid.UUID
    metodo_pago_id: uuid.UUID | None = Field(
        default=None, description="Con qué se le entrega; por defecto, efectivo"
    )
    monto: Pesos | None = Field(
        default=None, gt=0, description="Opcional: debe coincidir con lo pendiente"
    )
