import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.shared.dinero import Cantidad, CostoUnitario
from app.shared.esquemas import EdicionParcial

TipoItem = Literal["insumo", "producto"]
MotivoMerma = Literal["vencido", "danado", "error_preparacion", "degustacion"]


# --- Insumos y presentaciones ---------------------------------------------------------------


class PresentacionCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    factor: Cantidad = Field(
        gt=0, description="Unidades base por presentación (Bulto 50 kg → 50000)"
    )


class PresentacionEditar(EdicionParcial):
    NO_NULOS = ("nombre", "factor", "activa")

    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    factor: Cantidad | None = Field(default=None, gt=0)
    activa: bool | None = None


class PresentacionSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    factor: Cantidad
    activa: bool


class InsumoCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    unidad_base: str = Field(description="g, ml o und")
    stock_minimo: Cantidad = Field(default=Decimal(0), ge=0)
    dias_alerta_vencimiento: int | None = Field(default=None, ge=0, le=365)
    presentaciones: list[PresentacionCrear] = Field(default_factory=list)


class InsumoEditar(EdicionParcial):
    NO_NULOS = ("nombre", "unidad_base", "stock_minimo", "activo")

    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    unidad_base: str | None = None
    stock_minimo: Cantidad | None = Field(default=None, ge=0)
    dias_alerta_vencimiento: int | None = Field(default=None, ge=0, le=365)
    activo: bool | None = None


class InsumoSalida(BaseModel):
    id: uuid.UUID
    nombre: str
    unidad_base: str
    stock_minimo: Cantidad
    dias_alerta_vencimiento: int | None
    activo: bool
    presentaciones: list[PresentacionSalida]


# --- Lotes, kardex y stock ------------------------------------------------------------------


class LoteSalida(BaseModel):
    id: uuid.UUID
    origen: str
    origen_id: uuid.UUID | None
    cantidad_inicial: Cantidad
    cantidad_disponible: Cantidad
    costo_unitario: CostoUnitario
    fecha_ingreso: datetime
    fecha_vencimiento: date | None
    vencido: bool
    se_usa_primero: bool
    proveedor: str | None = None


class MovimientoSalida(BaseModel):
    id: uuid.UUID
    fecha: datetime
    tipo: str
    tipo_item: str
    item_id: uuid.UUID
    item_nombre: str | None = None
    lote_id: uuid.UUID
    cantidad: Cantidad
    costo_unitario: CostoUnitario
    costo_total: int
    referencia_tipo: str
    referencia_id: uuid.UUID
    usuario: str | None = None
    saldo_cantidad: Cantidad | None = None
    saldo_costo: int | None = None


EstadoStock = Literal["bien", "bajo_minimo", "por_vencer", "vencido"]


class StockItem(BaseModel):
    tipo_item: TipoItem
    item_id: uuid.UUID
    nombre: str
    unidad: str
    cantidad: Cantidad
    cantidad_vencida: Cantidad
    minimo: Cantidad
    proximo_vencimiento: date | None
    estado: EstadoStock
    valor: int
    lotes: int
    usado_en_recetas: int


class Kpis(BaseModel):
    valor_inventario: int
    bajo_minimo: list[str]
    lotes_por_vencer: int
    por_vencer: list[str]
    mermas_mes: int


class Alerta(BaseModel):
    tipo: Literal["bajo_minimo", "por_vencer", "vencido", "faltante", "verificacion"]
    tipo_item: TipoItem | None = None
    item_id: uuid.UUID | None = None
    titulo: str
    detalle: str
    lote_id: uuid.UUID | None = None


# --- Mermas y ajustes -----------------------------------------------------------------------


class MermaCrear(BaseModel):
    tipo_item: TipoItem
    item_id: uuid.UUID
    lote_id: uuid.UUID | None = None
    cantidad: Cantidad = Field(gt=0)
    motivo: MotivoMerma
    nota: str | None = Field(default=None, max_length=200)


class MermaSalida(BaseModel):
    id: uuid.UUID
    tipo_item: str
    item_id: uuid.UUID
    item_nombre: str | None = None
    lote_id: uuid.UUID | None
    cantidad: Cantidad
    motivo: str
    nota: str | None
    costo_total: int
    fecha: datetime


class AjusteCrear(BaseModel):
    tipo_item: TipoItem
    item_id: uuid.UUID
    cantidad_contada: Cantidad = Field(ge=0)
    motivo: str = Field(min_length=3, max_length=200)
    costo_unitario: CostoUnitario | None = Field(
        default=None, ge=0, description="Solo si el ítem no tiene lotes anteriores"
    )


class AjusteSalida(BaseModel):
    id: uuid.UUID
    tipo_item: str
    item_id: uuid.UUID
    cantidad_sistema: Cantidad
    cantidad_contada: Cantidad
    diferencia: Cantidad
    cantidad_vencida: Cantidad = Field(
        description="Vencido sin dar de baja: no entra al conteo, se da de baja como merma"
    )
    costo_total: int
    motivo: str
    fecha: datetime
