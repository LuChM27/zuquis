"""Esquema de cada clave de configuración (RF-44, RF-46). Agregar una clave nueva aquí la
hace disponible en GET/PATCH /configuracion con su valor por defecto."""

import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.shared.dinero import Porcentaje


class DatosNegocio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(default="Zuqui's Repostería", max_length=120)
    logo_url: str | None = Field(default=None, max_length=300)
    nit: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=200)
    telefono: str | None = Field(default=None, max_length=40)


class Impuestos(BaseModel):
    """Preparado para la facturación electrónica. Desactivado hasta que el contador defina el
    régimen (issue #1)."""

    model_config = ConfigDict(extra="forbid")

    activo: bool = False
    tipo: Literal["iva", "impuesto_consumo"] | None = None
    tarifa: Porcentaje = Decimal(0)
    precios_incluyen_impuesto: bool = True


CLAVES: dict[str, tuple[TypeAdapter, Any]] = {
    "negocio": (TypeAdapter(DatosNegocio), DatosNegocio()),
    # Tope de descuento por rol en porcentaje: {rol_id: "10"} (RN-16).
    "tope_descuento_por_rol": (TypeAdapter(dict[uuid.UUID, Porcentaje]), {}),
    "dias_alerta_vencimiento": (TypeAdapter(int), 3),
    "permitir_venta_sin_stock": (TypeAdapter(bool), False),
    "impuestos": (TypeAdapter(Impuestos), Impuestos()),
}


class MetodoPagoSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    es_efectivo: bool
    titular: str
    cuenta_puc: str | None
    activo: bool
    orden: int


Titular = Literal["negocio", "dueno"]


class MetodoPagoCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    es_efectivo: bool = False
    titular: Titular = "negocio"
    cuenta_puc: str | None = Field(default=None, max_length=10, pattern=r"^\d{1,10}$")
    orden: int = 0


class MetodoPagoEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=60)
    titular: Titular | None = None
    cuenta_puc: str | None = Field(default=None, max_length=10, pattern=r"^\d{1,10}$")
    activo: bool | None = None
    orden: int | None = None


class SedeSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    direccion: str | None
    telefono: str | None
    activa: bool


class SedeCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    direccion: str | None = Field(default=None, max_length=200)
    telefono: str | None = Field(default=None, max_length=40)


class SedeEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    direccion: str | None = Field(default=None, max_length=200)
    telefono: str | None = Field(default=None, max_length=40)
    activa: bool | None = None


class UnidadSalida(BaseModel):
    codigo: str
    nombre: str
