import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.shared.dinero import Cantidad, CostoUnitario, Pesos
from app.shared.esquemas import EdicionParcial

TipoProducto = Literal["preparado", "lote"]


class CategoriaCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    orden: int = 0
    icono: str | None = Field(default=None, max_length=40)


class CategoriaEditar(EdicionParcial):
    NO_NULOS = ("nombre", "orden", "activa")

    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    orden: int | None = None
    icono: str | None = Field(default=None, max_length=40)
    activa: bool | None = None


class CategoriaSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    orden: int
    icono: str | None
    activa: bool


class ModificadorCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    precio: Pesos = Field(ge=0)


class ModificadorEditar(EdicionParcial):
    NO_NULOS = ("nombre", "precio", "activo")

    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    precio: Pesos | None = Field(default=None, ge=0)
    activo: bool | None = None


class ModificadorSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    precio: int
    activo: bool
    tiene_receta: bool = False


class ProductoCrear(BaseModel):
    categoria_id: uuid.UUID
    nombre: str = Field(min_length=2, max_length=120)
    tipo: TipoProducto
    precio: Pesos = Field(ge=0)
    foto_url: str | None = Field(default=None, max_length=300)
    stock_minimo: Cantidad = Field(default=Decimal(0), ge=0)
    dias_vida_util: int | None = Field(default=None, ge=0, le=365)
    modificador_ids: list[uuid.UUID] = Field(default_factory=list)


class ProductoEditar(EdicionParcial):
    NO_NULOS = ("categoria_id", "nombre", "tipo", "precio", "disponible", "activo", "stock_minimo")

    categoria_id: uuid.UUID | None = None
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    tipo: TipoProducto | None = None
    precio: Pesos | None = Field(default=None, ge=0)
    foto_url: str | None = Field(default=None, max_length=300)
    disponible: bool | None = None
    activo: bool | None = None
    stock_minimo: Cantidad | None = Field(default=None, ge=0)
    dias_vida_util: int | None = Field(default=None, ge=0, le=365)
    modificador_ids: list[uuid.UUID] | None = None


class ProductoSalida(BaseModel):
    id: uuid.UUID
    categoria_id: uuid.UUID
    nombre: str
    tipo: TipoProducto
    precio: int
    foto_url: str | None
    disponible: bool
    activo: bool
    stock_minimo: Cantidad
    dias_vida_util: int | None
    modificadores: list[ModificadorSalida]
    tiene_receta: bool = False
    stock: Cantidad | None = Field(default=None, description="Unidades en vitrina (tipo lote)")


class PrecioHistorialSalida(BaseModel):
    precio_anterior: int | None
    precio_nuevo: int
    usuario: str | None
    fecha: datetime


# --- Recetas --------------------------------------------------------------------------------


class RecetaItemEntrada(BaseModel):
    insumo_id: uuid.UUID
    cantidad: Cantidad = Field(gt=0, description="En la unidad base del insumo")


class RecetaEntrada(BaseModel):
    rendimiento: Cantidad = Field(gt=0, description="Unidades que produce la receta")
    items: list[RecetaItemEntrada] = Field(min_length=1)


class RecetaItemSalida(BaseModel):
    insumo_id: uuid.UUID
    insumo: str
    unidad: str
    cantidad: Cantidad


class RecetaSalida(BaseModel):
    id: uuid.UUID
    version: int
    vigente: bool
    rendimiento: Cantidad
    creado_en: datetime
    items: list[RecetaItemSalida]


class CostoItem(BaseModel):
    insumo_id: uuid.UUID
    insumo: str
    unidad: str
    cantidad: Cantidad
    costo_unitario: CostoUnitario | None = Field(description="Último costo de compra")
    costo: int | None


class CostoSalida(BaseModel):
    """Costo teórico con el último costo de compra (RF-07). Es una referencia para fijar
    precios; el costo real sale por PEPS."""

    receta_id: uuid.UUID
    version: int
    rendimiento: Cantidad
    items: list[CostoItem]
    completo: bool = Field(description="False si algún insumo nunca se ha comprado")
    costo_receta: int
    costo_unitario: CostoUnitario
    costo_por_unidad: int
    precio: int
    margen: int
    margen_porcentaje: Cantidad | None = Field(description="Margen sobre el precio, en %")
