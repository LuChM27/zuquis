"""Cifras de los reportes: la ÚNICA fuente de cada número (spec fase 4, §4.1).

Tablas, Excel, PDF, gráficos y dashboard llaman a estas funciones; nadie repite una consulta
que dé una cifra que ya sale de aquí. Todo se agrega en PostgreSQL (``GROUP BY``), nunca
trayendo filas a Python para sumarlas.

Definiciones:
- Venta = ``ventas.total`` de las pagadas (ya sin propina ni domicilio). Encargos: el día de la
  entrega, que es cuando se crea su venta (RN-20).
- Cortesía = venta pagada con ``subtotal > 0`` y ``total = 0``. Su costo es gasto de cortesía
  (RN-17), no costo de insumos.
- Por producto y categoría se reporta el valor de las líneas (``venta_items.subtotal``), antes
  del descuento sobre el total de la venta, que no se reparte por línea: ese descuento sale en
  ``descuento_global`` y las tablas lo restan en una fila aparte para que cuadren.
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import Integer, String, and_, case, cast, func, literal, not_, select
from sqlalchemy.orm import Session

from app.core.config import obtener_config
from app.modules.auth.models import Usuario
from app.modules.carta.models import Categoria, Producto
from app.modules.configuracion.models import MetodoPago
from app.modules.encargos.models import Encargo
from app.modules.gastos.models import Gasto
from app.modules.inventario.models import Merma
from app.modules.reportes.periodo import Periodo
from app.modules.ventas.models import Venta, VentaItem, VentaItemModificador, VentaPago
from app.modules.ventas.service import PREFIJO_DECORACION

AgrupaVentas = Literal[
    "dia", "semana", "hora", "dia_semana_hora", "producto", "categoria", "metodo", "servicio",
    "cajero",
]  # fmt: skip

SERVICIOS = {"local": "En local", "llevar": "Para llevar", "domicilio": "Domicilio"}


class Totales(BaseModel):
    ventas: int
    n_ventas: int
    n_cortesias: int
    costo_insumos: int
    costo_cortesias: int
    descuentos: int
    propinas: int
    domicilios: int
    gastos: int
    mermas: int
    ingresos_cancelacion: int
    anuladas: int


class FilaVentas(BaseModel):
    clave: str
    etiqueta: str
    ventas: int
    costo: int
    unidades: Decimal = Decimal(0)
    n: int


def es_cortesia():
    return and_(Venta.subtotal > 0, Venta.total == 0)


def local(columna):
    """La marca de tiempo en hora local del negocio (para agrupar por día u hora)."""
    return func.timezone(obtener_config().zona_horaria, columna)


def _del_periodo(p: Periodo, estado: str = "pagada") -> list:
    inicio, fin = p.limites()
    filtro = [
        Venta.sede_id == p.sede_id,
        Venta.fecha >= inicio,
        Venta.fecha < fin,
        Venta.estado == estado,
    ]
    if p.caja_sesion_id:
        filtro.append(Venta.caja_sesion_id == p.caja_sesion_id)
    return filtro


def _suma(expr):
    return func.coalesce(func.sum(expr), 0)


def totales(db: Session, p: Periodo) -> Totales:
    cortesia = es_cortesia()
    v = db.execute(
        select(
            _suma(Venta.total),
            func.count(),
            _suma(case((cortesia, 1), else_=0)),
            _suma(case((cortesia, 0), else_=Venta.costo_total)),
            _suma(case((cortesia, Venta.costo_total), else_=0)),
            _suma(Venta.descuento_total),
            _suma(Venta.propina),
            _suma(Venta.valor_domicilio),
        ).where(*_del_periodo(p))
    ).one()
    anuladas = db.scalar(select(func.count()).where(*_del_periodo(p, "anulada")))
    gastos_filtro = [
        Gasto.sede_id == p.sede_id,
        Gasto.fecha >= p.desde,
        Gasto.fecha <= p.hasta,
        Gasto.estado == "registrado",
    ]
    if p.caja_sesion_id:
        gastos_filtro.append(Gasto.caja_sesion_id == p.caja_sesion_id)
    gastos = db.scalar(select(_suma(Gasto.monto)).where(*gastos_filtro))
    if p.caja_sesion_id:
        # Mermas y cancelaciones son de la sede, no de una caja: el cajero no las ve.
        mermas = retenido = 0
    else:
        mermas, retenido = _mermas_y_retenido(db, p)
    return Totales(
        ventas=int(v[0]),
        n_ventas=int(v[1]),
        n_cortesias=int(v[2]),
        costo_insumos=int(v[3]),
        costo_cortesias=int(v[4]),
        descuentos=int(v[5]),
        propinas=int(v[6]),
        domicilios=int(v[7]),
        gastos=int(gastos),
        mermas=int(mermas),
        ingresos_cancelacion=int(retenido),
        anuladas=int(anuladas or 0),
    )


def _mermas_y_retenido(db: Session, p: Periodo) -> tuple[int, int]:
    inicio, fin = p.limites()
    mermas = db.scalar(
        select(_suma(Merma.costo_total)).where(
            Merma.sede_id == p.sede_id, Merma.fecha >= inicio, Merma.fecha < fin
        )
    )
    retenido = db.scalar(
        select(_suma(Encargo.monto_retenido)).where(
            Encargo.sede_id == p.sede_id,
            Encargo.estado == "cancelado",
            Encargo.cancelado_en >= inicio,
            Encargo.cancelado_en < fin,
        )
    )
    return int(mermas), int(retenido)


def descuento_global(db: Session, p: Periodo) -> int:
    """Descuentos sobre el total de la venta (no repartidos por línea), sin cortesías: el
    descuento total de las ventas menos el de sus líneas."""
    ventas = (*_del_periodo(p), not_(es_cortesia()))
    total = db.scalar(select(_suma(Venta.descuento_total)).where(*ventas))
    por_linea = db.scalar(
        select(_suma(VentaItem.descuento))
        .join(Venta, Venta.id == VentaItem.venta_id)
        .where(*ventas)
    )
    return int(total) - int(por_linea)


def _por_venta(db: Session, p: Periodo, clave, etiqueta=None) -> list[FilaVentas]:
    """Agrupaciones a nivel de venta (día, hora, servicio, cajero)."""
    etiqueta = clave if etiqueta is None else etiqueta
    filas = db.execute(
        select(
            clave,
            etiqueta,
            _suma(Venta.total),
            _suma(case((es_cortesia(), 0), else_=Venta.costo_total)),
            func.count(),
        )
        .where(*_del_periodo(p))
        .group_by(clave, etiqueta)
        .order_by(clave)
    ).all()
    return [
        FilaVentas(clave=str(c), etiqueta=str(e), ventas=int(v), costo=int(k), n=int(n))
        for c, e, v, k, n in filas
    ]


def _costo_mods():
    """Costo de los modificadores por línea, agrupado una vez (se une con LEFT JOIN)."""
    return (
        select(
            VentaItemModificador.venta_item_id.label("item_id"),
            func.sum(VentaItemModificador.costo_total).label("costo"),
        )
        .group_by(VentaItemModificador.venta_item_id)
        .subquery()
    )


def _nombre_item():
    return func.coalesce(
        Producto.nombre,
        case(
            (VentaItem.descripcion.startswith(PREFIJO_DECORACION), "Decoración"),
            else_=VentaItem.descripcion,
        ),
    )


def _por_item(db: Session, p: Periodo, clave, etiqueta) -> list[FilaVentas]:
    """Agrupaciones por línea (producto, categoría), sin cortesías."""
    mods = _costo_mods()
    filas = db.execute(
        select(
            clave,
            etiqueta,
            _suma(VentaItem.subtotal),
            _suma(VentaItem.costo_total + func.coalesce(mods.c.costo, 0)),
            _suma(VentaItem.cantidad),
            func.count(func.distinct(VentaItem.venta_id)),
        )
        .join(Venta, Venta.id == VentaItem.venta_id)
        .outerjoin(mods, mods.c.item_id == VentaItem.id)
        .outerjoin(Producto, Producto.id == VentaItem.producto_id)
        .outerjoin(Categoria, Categoria.id == Producto.categoria_id)
        .where(*_del_periodo(p), not_(es_cortesia()))
        .group_by(clave, etiqueta)
        .order_by(_suma(VentaItem.subtotal).desc(), etiqueta)
    ).all()
    return [
        FilaVentas(clave=str(c), etiqueta=str(e), ventas=int(v), costo=int(k), unidades=u, n=int(n))
        for c, e, v, k, u, n in filas
    ]


def ventas_por(db: Session, p: Periodo, por: AgrupaVentas) -> list[FilaVentas]:
    momento = local(Venta.fecha)
    if por == "dia":
        return _por_venta(db, p, func.to_char(momento, "YYYY-MM-DD"))
    if por == "semana":
        return _por_venta(db, p, func.to_char(momento, 'IYYY-"W"IW'))
    if por == "hora":
        return _por_venta(db, p, cast(func.extract("hour", momento), Integer))
    if por == "dia_semana_hora":
        clave = func.concat(
            cast(cast(func.extract("isodow", momento), Integer), String),
            "-",
            cast(cast(func.extract("hour", momento), Integer), String),
        )
        return _por_venta(db, p, clave)
    if por == "servicio":
        filas = _por_venta(db, p, Venta.tipo_servicio)
        return [f.model_copy(update={"etiqueta": SERVICIOS.get(f.clave, f.clave)}) for f in filas]
    if por == "cajero":
        return _por_venta_cajero(db, p)
    if por == "metodo":
        return _por_metodo(db, p)
    if por == "producto":
        clave = func.coalesce(cast(VentaItem.producto_id, String), _nombre_item())
        return _por_item(db, p, clave, _nombre_item())
    if por == "categoria":
        clave = func.coalesce(cast(Categoria.id, String), literal("sin"))
        return _por_item(db, p, clave, func.coalesce(Categoria.nombre, literal("Sin categoría")))
    raise ValueError(por)


def _por_venta_cajero(db: Session, p: Periodo) -> list[FilaVentas]:
    filas = db.execute(
        select(
            Venta.usuario_id,
            Usuario.nombre,
            _suma(Venta.total),
            _suma(case((es_cortesia(), 0), else_=Venta.costo_total)),
            func.count(),
        )
        .join(Usuario, Usuario.id == Venta.usuario_id)
        .where(*_del_periodo(p))
        .group_by(Venta.usuario_id, Usuario.nombre)
        .order_by(_suma(Venta.total).desc())
    ).all()
    return [
        FilaVentas(clave=str(c), etiqueta=e, ventas=int(v), costo=int(k), n=int(n))
        for c, e, v, k, n in filas
    ]


def _por_metodo(db: Session, p: Periodo) -> list[FilaVentas]:
    """Lo cobrado por método (``venta_pagos.monto``: incluye propina y domicilio)."""
    filas = db.execute(
        select(
            MetodoPago.id,
            MetodoPago.nombre,
            _suma(VentaPago.monto),
            func.count(func.distinct(VentaPago.venta_id)),
        )
        .join(Venta, Venta.id == VentaPago.venta_id)
        .join(MetodoPago, MetodoPago.id == VentaPago.metodo_pago_id)
        .where(*_del_periodo(p))
        .group_by(MetodoPago.id, MetodoPago.nombre, MetodoPago.orden)
        .order_by(MetodoPago.orden, MetodoPago.nombre)
    ).all()
    return [
        FilaVentas(clave=str(c), etiqueta=e, ventas=int(v), costo=0, n=int(n))
        for c, e, v, n in filas
    ]
