import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.shared.dinero import Cantidad, CostoUnitario


class ProduccionCrear(BaseModel):
    producto_id: uuid.UUID
    cantidad_producida: Cantidad = Field(gt=0)
    fecha_vencimiento: date | None = Field(
        default=None, description="Por defecto, hoy + días de vida útil del producto"
    )
    responsable_id: uuid.UUID | None = Field(
        default=None, description="Por defecto, quien registra"
    )


class ConsumoSalida(BaseModel):
    insumo_id: uuid.UUID
    insumo: str
    unidad: str
    cantidad: Cantidad
    costo_total: int


class ProduccionSalida(BaseModel):
    id: uuid.UUID
    producto_id: uuid.UUID
    producto: str
    receta_id: uuid.UUID
    receta_version: int
    cantidad_producida: Cantidad
    costo_total: int
    costo_unitario: CostoUnitario
    fecha_vencimiento: date | None
    lote_resultante_id: uuid.UUID | None
    responsable: str | None
    fecha: datetime
    anulada: bool
    motivo_anulacion: str | None
    consumos: list[ConsumoSalida]


class ProduccionVistaPrevia(BaseModel):
    """Lo que registraría la producción (insumos por PEPS y costo) sin registrarla."""

    producto_id: uuid.UUID
    producto: str
    receta_version: int
    cantidad_producida: Cantidad
    costo_total: int
    costo_unitario: CostoUnitario
    fecha_vencimiento: date | None
    consumos: list[ConsumoSalida]


class AnulacionEntrada(BaseModel):
    motivo: str = Field(min_length=3, max_length=200)
