"""Cifras de inventario: valorizado a una fecha, mermas y producido contra vendido.
Única fuente de estos números; todo se agrega en SQL."""

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.modules.carta.models import Producto
from app.modules.inventario.models import Insumo, Lote, Merma, MovimientoInventario
from app.modules.produccion.models import Produccion
from app.modules.reportes.cifras import _del_periodo
from app.modules.reportes.periodo import Periodo
from app.modules.ventas.models import Venta, VentaItem
from app.shared.dinero import costo_linea
from app.shared.fechas import zona

MOTIVOS = {
    "vencido": "Vencido",
    "danado": "Dañado",
    "error_preparacion": "Error de preparación",
    "degustacion": "Degustación",
}
TIPOS_ITEM = {"insumo": "Insumo", "producto": "Producto"}


def _con_nombre(consulta, tipo_item, item_id):
    """Une el insumo o el producto según ``tipo_item`` y devuelve (consulta, nombre)."""
    consulta = consulta.outerjoin(
        Insumo, and_(tipo_item == "insumo", Insumo.id == item_id)
    ).outerjoin(Producto, and_(tipo_item == "producto", Producto.id == item_id))
    return consulta, func.coalesce(Insumo.nombre, Producto.nombre)


class FilaValorizado(BaseModel):
    tipo_item: str
    item: str
    lote_id: uuid.UUID
    fecha_ingreso: datetime
    cantidad: Decimal
    costo_unitario: Decimal
    valor: int


def inventario_valorizado(db: Session, sede_id: uuid.UUID, corte: date) -> list[FilaValorizado]:
    """Existencias por lote al final del día ``corte``, reconstruidas desde el libro de
    movimientos (sirve para fechas pasadas). Cada lote se redondea a peso una sola vez."""
    fin = datetime.combine(corte + timedelta(days=1), time(), tzinfo=zona())
    cantidad = func.sum(MovimientoInventario.cantidad)
    consulta = select(Lote.id, Lote.tipo_item, Lote.fecha_ingreso, Lote.costo_unitario).join(
        MovimientoInventario, MovimientoInventario.lote_id == Lote.id
    )
    consulta, nombre = _con_nombre(consulta, Lote.tipo_item, Lote.item_id)
    filas = db.execute(
        consulta.add_columns(nombre, cantidad)
        .where(MovimientoInventario.sede_id == sede_id, MovimientoInventario.fecha < fin)
        .group_by(Lote.id, Lote.tipo_item, Lote.fecha_ingreso, Lote.costo_unitario, nombre)
        .having(cantidad > 0)
        .order_by(Lote.tipo_item, nombre, Lote.fecha_ingreso)
    ).all()
    return [
        FilaValorizado(
            tipo_item=t,
            item=n,
            lote_id=lote_id,
            fecha_ingreso=f,
            cantidad=c,
            costo_unitario=cu,
            valor=costo_linea(c, cu),
        )
        for lote_id, t, f, cu, n, c in filas
    ]


class FilaMerma(BaseModel):
    motivo: str
    tipo_item: str
    item: str
    cantidad: Decimal
    costo: int


def mermas_por(db: Session, p: Periodo) -> list[FilaMerma]:
    """Mermas por motivo e ítem, en pesos (gasto aparte del costo de ventas, #1)."""
    inicio, fin = p.limites()
    consulta, nombre = _con_nombre(
        select(Merma.motivo, Merma.tipo_item), Merma.tipo_item, Merma.item_id
    )
    filas = db.execute(
        consulta.add_columns(nombre, func.sum(Merma.cantidad), func.sum(Merma.costo_total))
        .where(Merma.sede_id == p.sede_id, Merma.fecha >= inicio, Merma.fecha < fin)
        .group_by(Merma.motivo, Merma.tipo_item, nombre)
        .order_by(func.sum(Merma.costo_total).desc())
    ).all()
    return [
        FilaMerma(motivo=MOTIVOS.get(m, m), tipo_item=t, item=n, cantidad=c, costo=int(k))
        for m, t, n, c, k in filas
    ]


class FilaProducido(BaseModel):
    producto: str
    producido: Decimal
    vendido: Decimal


def producido_vs_vendido(db: Session, p: Periodo) -> list[FilaProducido]:
    """Productos de vitrina (tipo lote): lo producido (sin anuladas) contra lo vendido en el
    rango (ventas pagadas, cortesías incluidas: también salen de la vitrina)."""
    inicio, fin = p.limites()
    producido = dict(
        db.execute(
            select(Produccion.producto_id, func.sum(Produccion.cantidad_producida))
            .where(
                Produccion.sede_id == p.sede_id,
                ~Produccion.anulada,
                Produccion.fecha >= inicio,
                Produccion.fecha < fin,
            )
            .group_by(Produccion.producto_id)
        ).all()
    )
    vendido = dict(
        db.execute(
            select(VentaItem.producto_id, func.sum(VentaItem.cantidad))
            .join(Venta, Venta.id == VentaItem.venta_id)
            .where(*_del_periodo(p), VentaItem.producto_id.is_not(None))
            .group_by(VentaItem.producto_id)
        ).all()
    )
    ids = set(producido) | set(vendido)
    if not ids:
        return []
    productos = db.execute(
        select(Producto.id, Producto.nombre)
        .where(Producto.id.in_(ids), Producto.tipo == "lote")
        .order_by(Producto.nombre)
    ).all()
    cero = Decimal(0)
    return [
        FilaProducido(
            producto=nombre, producido=producido.get(i, cero), vendido=vendido.get(i, cero)
        )
        for i, nombre in productos
    ]
