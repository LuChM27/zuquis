import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.shared.dinero import Pesos


class AbrirCaja(BaseModel):
    base_inicial: Pesos = Field(ge=0, description="Efectivo con el que arranca la caja")


class MovimientoManual(BaseModel):
    tipo: Literal["entrada_manual", "salida_manual"]
    metodo_pago_id: uuid.UUID
    monto: Pesos = Field(gt=0, description="Siempre positivo; la salida se guarda negativa")
    motivo: str = Field(min_length=3, max_length=200)


class SesionSalida(BaseModel):
    id: uuid.UUID
    estado: str
    abierta_en: datetime
    abierta_por: uuid.UUID
    responsable: str | None
    base_inicial: int
    cerrada_en: datetime | None
    cerrada_por: uuid.UUID | None
    observacion: str | None


class MovimientoSalida(BaseModel):
    id: uuid.UUID
    caja_sesion_id: uuid.UUID
    tipo: str
    metodo_pago_id: uuid.UUID
    metodo: str | None = None
    monto: int
    referencia_tipo: str | None
    referencia_id: uuid.UUID | None
    motivo: str | None
    usuario: str | None = None
    fecha: datetime


class EsperadoMetodo(BaseModel):
    metodo_pago_id: uuid.UUID
    metodo: str
    es_efectivo: bool
    esperado: int


class EstadoCaja(BaseModel):
    abierta: bool
    sesion: SesionSalida | None = None
    esperado: list[EsperadoMetodo] = Field(default_factory=list)
