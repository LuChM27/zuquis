import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.shared.dinero import Cantidad, Pesos

TipoServicio = Literal["local", "llevar", "domicilio"]


class DescuentoEntrada(BaseModel):
    """Descuento por valor (pesos) o porcentaje, siempre con motivo (RF-11)."""

    tipo: Literal["valor", "porcentaje"]
    valor: Decimal = Field(gt=0, description="Pesos si es por valor; % si es porcentaje")
    motivo: str = Field(min_length=3, max_length=200)

    @model_validator(mode="after")
    def _rango(self):
        if self.tipo == "porcentaje" and self.valor > 100:
            raise ValueError("El porcentaje de descuento no puede pasar de 100.")
        if self.tipo == "valor" and self.valor != self.valor.to_integral_value():
            raise ValueError("Un descuento por valor va en pesos enteros.")
        return self


class ItemEntrada(BaseModel):
    producto_id: uuid.UUID
    cantidad: Cantidad = Field(gt=0)
    modificador_ids: list[uuid.UUID] = Field(default_factory=list)
    nota: str | None = Field(default=None, max_length=200)
    descuento: DescuentoEntrada | None = None


class PagoEntrada(BaseModel):
    metodo_pago_id: uuid.UUID
    monto: Pesos = Field(gt=0)
    recibido: Pesos | None = Field(default=None, description="Solo efectivo: con cuánto paga")


class AutorizacionEntrada(BaseModel):
    """Credencial de quien autoriza un descuento por encima del tope del rol (RN-16)."""

    email: str = Field(min_length=3, max_length=200)
    clave: str = Field(min_length=1, max_length=200)


class VentaCrear(BaseModel):
    tipo_servicio: TipoServicio = "local"
    cliente_id: uuid.UUID | None = None
    items: list[ItemEntrada] = Field(min_length=1, max_length=100)
    descuento: DescuentoEntrada | None = Field(default=None, description="Sobre toda la venta")
    propina: Pesos = Field(default=0, ge=0)
    valor_domicilio: Pesos = Field(default=0, ge=0)
    pagos: list[PagoEntrada] = Field(
        default_factory=list, max_length=10, description="Vacío solo si se cobra $0 (cortesía)"
    )
    autorizacion: AutorizacionEntrada | None = Field(
        default=None, description="Solo si algún descuento supera el tope del rol"
    )

    @model_validator(mode="after")
    def _domicilio(self):
        if self.valor_domicilio and self.tipo_servicio != "domicilio":
            raise ValueError("El valor del domicilio solo aplica a ventas a domicilio.")
        return self


class AnulacionEntrada(BaseModel):
    motivo: str = Field(min_length=3, max_length=200)


class ModificadorSalida(BaseModel):
    modificador_id: uuid.UUID
    nombre: str
    precio: int
    costo_total: int


class ItemSalida(BaseModel):
    id: uuid.UUID
    producto_id: uuid.UUID
    producto: str
    cantidad: Cantidad
    precio_unitario: int
    modificadores: list[ModificadorSalida]
    bruto: int
    descuento: int
    subtotal: int
    costo_total: int
    nota: str | None


class PagoSalida(BaseModel):
    metodo_pago_id: uuid.UUID
    metodo: str
    monto: int
    recibido: int | None
    cambio: int


class VentaSalida(BaseModel):
    id: uuid.UUID
    numero: int
    fecha: datetime
    caja_sesion_id: uuid.UUID
    tipo_servicio: str
    cliente_id: uuid.UUID | None
    items: list[ItemSalida]
    subtotal: int
    descuento_total: int
    descuento_motivo: str | None
    descuento_autorizado_por: uuid.UUID | None
    cortesia: bool = Field(description="Descuento del 100 %: su costo es gasto de cortesía")
    total: int
    propina: int
    valor_domicilio: int
    cobrado: int = Field(description="total + propina + domicilio = Σ pagos")
    cambio: int
    costo_total: int
    pagos: list[PagoSalida]
    estado: str
    cajero: str | None
    motivo_anulacion: str | None
    anulada_en: datetime | None
