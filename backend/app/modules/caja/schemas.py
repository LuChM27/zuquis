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


# --- Cierre (#32) ---------------------------------------------------------------------------


class ContadoMetodo(BaseModel):
    metodo_pago_id: uuid.UUID
    contado: Pesos = Field(ge=0)


class CerrarCaja(BaseModel):
    contado: list[ContadoMetodo] = Field(min_length=1)
    observacion: str | None = Field(default=None, max_length=500)


class LineaEfectivo(BaseModel):
    """Una línea de "De dónde sale el efectivo"."""

    concepto: str
    monto: int


class ResumenTurno(BaseModel):
    ventas: int
    abonos: int
    propinas: int
    gastos: int
    domicilios_entregados: int
    pagos_proveedores: int
    anulaciones: int


class ArqueoSalida(BaseModel):
    metodo_pago_id: uuid.UUID
    metodo: str
    es_efectivo: bool
    esperado: int
    contado: int | None = None
    diferencia: int | None = None


class VistaCierre(BaseModel):
    sesion: SesionSalida
    arqueo: list[ArqueoSalida]
    efectivo: list[LineaEfectivo]
    efectivo_esperado: int
    resumen: ResumenTurno
    domicilios_sin_liquidar: int = 0


class SesionResumen(SesionSalida):
    efectivo_esperado: int
    diferencia_total: int | None


class SesionDetalle(SesionResumen):
    arqueos: list[ArqueoSalida]
    efectivo: list[LineaEfectivo]
    resumen: ResumenTurno
