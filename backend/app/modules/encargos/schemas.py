import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.modules.domicilios.schemas import DomicilioEntrada
from app.modules.ventas.schemas import PagoEntrada
from app.shared.dinero import Cantidad, Pesos

Estado = Literal["pendiente", "en_produccion", "listo", "entregado", "cancelado"]
TipoEntrega = Literal["recoge", "domicilio"]
Decision = Literal["devuelve_total", "devuelve_parcial", "retiene"]


class ItemEntrada(BaseModel):
    """Con `producto_id` sale de la carta; sin él es un detalle personalizado."""

    producto_id: uuid.UUID | None = None
    descripcion: str | None = Field(default=None, max_length=200)
    cantidad: Cantidad = Field(gt=0)
    precio: Pesos | None = Field(
        default=None, ge=0, description="Por unidad. Por defecto, el de la carta"
    )

    @model_validator(mode="after")
    def _personalizado(self):
        if self.producto_id is None:
            if not (self.descripcion or "").strip():
                raise ValueError("Un ítem sin producto necesita descripción.")
            if self.precio is None:
                raise ValueError("Un ítem sin producto necesita precio.")
        return self


class AbonoEntrada(BaseModel):
    monto: Pesos = Field(gt=0)
    metodo_pago_id: uuid.UUID


class EncargoCrear(BaseModel):
    cliente_id: uuid.UUID
    descripcion: str | None = Field(
        default=None, max_length=200, description="Por defecto se arma con los ítems"
    )
    fecha_entrega: datetime
    tipo_entrega: TipoEntrega = "recoge"
    direccion_entrega: str | None = Field(default=None, max_length=200)
    observaciones: str | None = Field(default=None, max_length=500)
    items: list[ItemEntrada] = Field(min_length=1, max_length=50)
    abono: AbonoEntrada | None = Field(default=None, description="Abono inicial, opcional")


class EncargoEditar(BaseModel):
    cliente_id: uuid.UUID | None = None
    descripcion: str | None = Field(default=None, max_length=200)
    fecha_entrega: datetime | None = None
    tipo_entrega: TipoEntrega | None = None
    direccion_entrega: str | None = Field(default=None, max_length=200)
    observaciones: str | None = Field(default=None, max_length=500)
    items: list[ItemEntrada] | None = Field(default=None, min_length=1, max_length=50)


class CambioEstado(BaseModel):
    estado: Estado


class AnulacionAbono(BaseModel):
    motivo: str = Field(min_length=3, max_length=200)


class EntregaEntrada(BaseModel):
    pagos: list[PagoEntrada] = Field(
        default_factory=list, max_length=10, description="Cubren el saldo más el domicilio"
    )
    valor_domicilio: Pesos = Field(default=0, ge=0)
    domicilio: DomicilioEntrada | None = Field(
        default=None, description="Obligatorio si el encargo se entrega a domicilio"
    )


class CancelacionEntrada(BaseModel):
    """RN-22: por defecto se devuelve todo lo abonado. Retener todo o una parte es la excepción
    y exige motivo."""

    decision: Decision = "devuelve_total"
    monto_devuelto: Pesos | None = Field(default=None, ge=0)
    motivo: str | None = Field(default=None, max_length=200)
    metodo_pago_id: uuid.UUID | None = Field(
        default=None, description="Con qué se devuelve; por defecto, efectivo"
    )

    @model_validator(mode="after")
    def _excepcion(self):
        if self.decision != "devuelve_total" and len((self.motivo or "").strip()) < 3:
            raise ValueError("Retener el abono, todo o en parte, exige un motivo.")
        if self.decision == "devuelve_parcial" and not self.monto_devuelto:
            raise ValueError("Indica cuánto se devuelve.")
        return self


class ItemSalida(BaseModel):
    id: uuid.UUID
    producto_id: uuid.UUID | None
    descripcion: str
    cantidad: Cantidad
    precio: int
    subtotal: int


class AbonoSalida(BaseModel):
    id: uuid.UUID
    monto: int
    metodo_pago_id: uuid.UUID
    metodo: str
    fecha: datetime
    estado: str
    motivo_anulacion: str | None


class ClienteBreve(BaseModel):
    id: uuid.UUID
    nombre: str
    telefono: str | None
    direccion: str | None


class EncargoSalida(BaseModel):
    id: uuid.UUID
    numero: int
    cliente: ClienteBreve
    descripcion: str
    fecha_entrega: datetime
    tipo_entrega: str
    direccion_entrega: str | None
    observaciones: str | None
    items: list[ItemSalida]
    total: int
    abonado: int = Field(description="Σ abonos vigentes")
    saldo: int = Field(description="total − abonado; $0 si ya se entregó o se canceló")
    estado: str
    editable: bool = Field(description="Solo mientras está pendiente (RN-23)")
    abonos: list[AbonoSalida]
    creado_en: datetime
    venta_id: uuid.UUID | None
    venta_numero: int | None
    entregado_en: datetime | None
    decision_cancelacion: str | None
    monto_devuelto: int
    monto_retenido: int
    motivo_cancelacion: str | None
    cancelado_en: datetime | None


class ConteoDia(BaseModel):
    fecha: date
    encargos: int
