import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.shared.dinero import Cantidad, CostoUnitario, Pesos
from app.shared.esquemas import EdicionParcial


class ProveedorCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    nit_o_cedula: str | None = Field(default=None, max_length=30)
    telefono: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=200)
    insumo_ids: list[uuid.UUID] = Field(default_factory=list)


class ProveedorEditar(EdicionParcial):
    NO_NULOS = ("nombre", "activo", "insumo_ids")

    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    nit_o_cedula: str | None = Field(default=None, max_length=30)
    telefono: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=200)
    activo: bool | None = None
    insumo_ids: list[uuid.UUID] | None = None


class InsumoResumen(BaseModel):
    id: uuid.UUID
    nombre: str


class ProveedorSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    nit_o_cedula: str | None
    telefono: str | None
    email: str | None
    activo: bool
    insumos: list[InsumoResumen]


class CompraItemEntrada(BaseModel):
    insumo_id: uuid.UUID
    presentacion_id: uuid.UUID | None = Field(
        default=None, description="Sin presentación: unidad base"
    )
    cantidad: Cantidad = Field(gt=0, description="En la presentación (2 bultos)")
    costo_total: Pesos = Field(ge=0, description="Lo que costó la línea, en pesos")
    fecha_vencimiento: date | None = None


class CompraCrear(BaseModel):
    proveedor_id: uuid.UUID | None = None
    fecha: date | None = Field(default=None, description="Por defecto, hoy")
    numero_factura_proveedor: str | None = Field(default=None, max_length=60)
    soporte_url: str | None = Field(default=None, max_length=300)
    estado_pago: Literal["contado", "por_pagar"]
    metodo_pago_id: uuid.UUID | None = Field(
        default=None, description="Obligatorio si es de contado"
    )
    items: list[CompraItemEntrada] = Field(min_length=1)

    @model_validator(mode="after")
    def _metodo_si_contado(self):
        if self.estado_pago == "contado" and self.metodo_pago_id is None:
            raise ValueError("Una compra de contado necesita el método de pago.")
        return self


class CompraItemSalida(BaseModel):
    id: uuid.UUID
    insumo_id: uuid.UUID
    insumo: str
    unidad: str
    presentacion: str | None
    cantidad: Cantidad
    cantidad_base: Cantidad
    costo_total: int
    costo_unitario: CostoUnitario
    fecha_vencimiento: date | None
    lote_id: uuid.UUID | None


class PagoEntrada(BaseModel):
    monto: Pesos = Field(gt=0)
    metodo_pago_id: uuid.UUID


class PagoSalida(BaseModel):
    id: uuid.UUID
    fecha: datetime
    monto: int
    metodo_pago_id: uuid.UUID
    metodo_pago: str | None = None


class CompraSalida(BaseModel):
    id: uuid.UUID
    proveedor_id: uuid.UUID | None
    proveedor: str | None
    fecha: date
    numero_factura_proveedor: str | None
    total: int
    pagado: int
    saldo: int
    estado_pago: str
    soporte_url: str | None
    anulada: bool
    motivo_anulacion: str | None
    creado_en: datetime
    items: list[CompraItemSalida]
    pagos: list[PagoSalida]


class AnulacionEntrada(BaseModel):
    motivo: str = Field(min_length=3, max_length=200)


class CuentaPorPagar(BaseModel):
    proveedor_id: uuid.UUID | None
    proveedor: str
    compras: int
    saldo: int
    mas_antigua: date
