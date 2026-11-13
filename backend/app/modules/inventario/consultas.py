"""Consultas de inventario (#23, RF-32, RF-33): stock por ítem, lotes en orden PEPS, kardex,
movimientos, alertas y el resumen de la pantalla.

Lo vencido que aún no se ha dado de baja no cuenta como existencia (no se puede usar, RN-11),
pero sí se muestra aparte y vale a su costo hasta que se registre la merma.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.modules.auth.models import Usuario
from app.modules.carta.models import Producto, Receta, RecetaItem
from app.modules.compras.models import Compra, CompraItem, Proveedor
from app.modules.configuracion import service as configuracion
from app.modules.inventario.models import (
    FaltanteInventario,
    Insumo,
    Lote,
    Merma,
    MovimientoInventario,
    VerificacionInventario,
)
from app.modules.inventario.operaciones import nombre_item, nombres_items
from app.modules.inventario.schemas import (
    Alerta,
    Kpis,
    LoteSalida,
    MovimientoSalida,
    StockItem,
)
from app.shared.dinero import costo_linea
from app.shared.fechas import hoy, zona
from app.shared.paginacion import ParamsPagina, RangoFechas

CERO = Decimal(0)


def _num(cantidad: Decimal) -> str:
    """2000.0000 → "2000"; 2.5000 → "2.5"."""
    return format(cantidad.normalize(), "f")


@dataclass
class _Item:
    tipo_item: str
    item_id: uuid.UUID
    nombre: str
    unidad: str
    minimo: Decimal
    dias_alerta: int
    usado_en_recetas: int = 0
    lotes: list[Lote] = field(default_factory=list)

    def vencido(self, lote: Lote, dia: date) -> bool:
        return lote.fecha_vencimiento is not None and lote.fecha_vencimiento < dia

    def por_vencer(self, lote: Lote, dia: date) -> bool:
        return (
            lote.fecha_vencimiento is not None
            and not self.vencido(lote, dia)
            and (lote.fecha_vencimiento - dia).days <= self.dias_alerta
        )

    def stock(self, dia: date) -> StockItem:
        vigentes = [lote for lote in self.lotes if not self.vencido(lote, dia)]
        cantidad = sum((lote.cantidad_disponible for lote in vigentes), CERO)
        vencida = sum(
            (lote.cantidad_disponible for lote in self.lotes if self.vencido(lote, dia)), CERO
        )
        vencimientos = [lote.fecha_vencimiento for lote in vigentes if lote.fecha_vencimiento]
        if vencida > 0:
            estado = "vencido"
        elif self.bajo_minimo(cantidad):
            estado = "bajo_minimo"
        elif any(self.por_vencer(lote, dia) for lote in vigentes):
            estado = "por_vencer"
        else:
            estado = "bien"
        return StockItem(
            tipo_item=self.tipo_item,
            item_id=self.item_id,
            nombre=self.nombre,
            unidad=self.unidad,
            cantidad=cantidad,
            cantidad_vencida=vencida,
            minimo=self.minimo,
            proximo_vencimiento=min(vencimientos, default=None),
            estado=estado,
            valor=sum(
                costo_linea(lote.cantidad_disponible, lote.costo_unitario) for lote in self.lotes
            ),
            lotes=len(self.lotes),
            usado_en_recetas=self.usado_en_recetas,
        )

    def bajo_minimo(self, cantidad: Decimal) -> bool:
        return self.minimo > 0 and cantidad < self.minimo


def _items(db: Session, ctx: Contexto, tipo_item: str | None = None) -> list[_Item]:
    """Insumos activos y productos por lote activos de la sede, con sus lotes con existencia."""
    dias_general = configuracion.valor(db, ctx.sede_id, "dias_alerta_vencimiento")
    items: dict[tuple[str, uuid.UUID], _Item] = {}
    if tipo_item in (None, "insumo"):
        recetas = dict(
            db.execute(
                select(RecetaItem.insumo_id, func.count(func.distinct(Receta.id)))
                .join(Receta, Receta.id == RecetaItem.receta_id)
                .where(Receta.sede_id == ctx.sede_id, Receta.vigente)
                .group_by(RecetaItem.insumo_id)
            ).all()
        )
        for i in db.scalars(select(Insumo).where(Insumo.sede_id == ctx.sede_id, Insumo.activo)):
            items["insumo", i.id] = _Item(
                "insumo",
                i.id,
                i.nombre,
                i.unidad_base,
                i.stock_minimo,
                i.dias_alerta_vencimiento
                if i.dias_alerta_vencimiento is not None
                else dias_general,
                recetas.get(i.id, 0),
            )
    if tipo_item in (None, "producto"):
        for p in db.scalars(
            select(Producto).where(
                Producto.sede_id == ctx.sede_id, Producto.activo, Producto.tipo == "lote"
            )
        ):
            items["producto", p.id] = _Item(
                "producto", p.id, p.nombre, "und", p.stock_minimo, dias_general
            )

    consulta = select(Lote).where(Lote.sede_id == ctx.sede_id, Lote.cantidad_disponible > 0)
    if tipo_item:
        consulta = consulta.where(Lote.tipo_item == tipo_item)
    for lote in db.scalars(consulta.order_by(Lote.fecha_ingreso, Lote.id)):
        if (item := items.get((lote.tipo_item, lote.item_id))) is not None:
            item.lotes.append(lote)
    return sorted(items.values(), key=lambda i: (i.tipo_item, i.nombre.lower()))


# --- Stock y lotes --------------------------------------------------------------------------


def stock(db: Session, ctx: Contexto, tipo_item: str | None) -> list[StockItem]:
    dia = hoy()
    return [item.stock(dia) for item in _items(db, ctx, tipo_item)]


def lotes(db: Session, ctx: Contexto, tipo_item: str, item_id: uuid.UUID) -> list[LoteSalida]:
    """Lotes con existencia en orden PEPS; marca el que se usa primero (el vigente más antiguo)."""
    nombre_item(db, ctx, tipo_item, item_id)  # 404 si no existe en la sede
    dia = hoy()
    filas = db.execute(
        select(Lote, Proveedor.nombre)
        .outerjoin(CompraItem, CompraItem.lote_id == Lote.id)
        .outerjoin(Compra, Compra.id == CompraItem.compra_id)
        .outerjoin(Proveedor, Proveedor.id == Compra.proveedor_id)
        .where(
            Lote.sede_id == ctx.sede_id,
            Lote.tipo_item == tipo_item,
            Lote.item_id == item_id,
            Lote.cantidad_disponible > 0,
        )
        .order_by(Lote.fecha_ingreso, Lote.id)
    ).all()
    salidas = []
    primero_marcado = False
    for lote, proveedor in filas:
        vencido = lote.fecha_vencimiento is not None and lote.fecha_vencimiento < dia
        primero = not vencido and not primero_marcado
        primero_marcado = primero_marcado or primero
        salidas.append(
            LoteSalida(
                id=lote.id,
                origen=lote.origen,
                origen_id=lote.origen_id,
                cantidad_inicial=lote.cantidad_inicial,
                cantidad_disponible=lote.cantidad_disponible,
                costo_unitario=lote.costo_unitario,
                fecha_ingreso=lote.fecha_ingreso,
                fecha_vencimiento=lote.fecha_vencimiento,
                vencido=vencido,
                se_usa_primero=primero,
                proveedor=proveedor,
            )
        )
    return salidas


# --- Kardex y movimientos -------------------------------------------------------------------


def _con_saldos(sede_id: uuid.UUID) -> Select:
    """Movimientos de la sede con el saldo acumulado de su ítem en cada línea. Se calcula
    sobre todo el libro, así el saldo es correcto aunque luego se filtre por fecha o página."""
    m = MovimientoInventario
    ventana = {
        "partition_by": (m.tipo_item, m.item_id),
        "order_by": (m.fecha, m.id),
    }
    return select(
        m,
        func.sum(m.cantidad).over(**ventana).label("saldo_cantidad"),
        func.sum(m.costo_total).over(**ventana).label("saldo_costo"),
    ).where(m.sede_id == sede_id)


def movimientos(
    db: Session,
    ctx: Contexto,
    params: ParamsPagina,
    rango: RangoFechas,
    *,
    tipo_item: str | None = None,
    item_id: uuid.UUID | None = None,
    tipo: str | None = None,
    ascendente: bool = False,
) -> tuple[list[MovimientoSalida], int]:
    base = _con_saldos(ctx.sede_id).subquery()
    c = base.c
    consulta = select(base, Usuario.nombre.label("usuario")).outerjoin(
        Usuario, Usuario.id == c.usuario_id
    )
    if tipo_item:
        consulta = consulta.where(c.tipo_item == tipo_item)
    if item_id:
        consulta = consulta.where(c.item_id == item_id)
    if tipo:
        consulta = consulta.where(c.tipo == tipo)
    if rango.desde:
        consulta = consulta.where(c.fecha >= _inicio(rango.desde))
    if rango.hasta:
        consulta = consulta.where(c.fecha < _inicio(rango.hasta + timedelta(days=1)))
    orden = (c.fecha, c.id) if ascendente else (c.fecha.desc(), c.id.desc())
    consulta = consulta.order_by(*orden)

    total = db.scalar(select(func.count()).select_from(consulta.order_by(None).subquery()))
    filas = db.execute(consulta.limit(params.size).offset((params.page - 1) * params.size)).all()
    nombres = nombres_items(db, filas)
    salidas = [
        MovimientoSalida(
            id=f.id,
            fecha=f.fecha,
            tipo=f.tipo,
            tipo_item=f.tipo_item,
            item_id=f.item_id,
            item_nombre=nombres.get(f.item_id),
            lote_id=f.lote_id,
            cantidad=f.cantidad,
            costo_unitario=f.costo_unitario,
            costo_total=f.costo_total,
            referencia_tipo=f.referencia_tipo,
            referencia_id=f.referencia_id,
            usuario=f.usuario,
            saldo_cantidad=f.saldo_cantidad,
            saldo_costo=f.saldo_costo,
        )
        for f in filas
    ]
    return salidas, total or 0


def kardex(
    db: Session,
    ctx: Contexto,
    params: ParamsPagina,
    rango: RangoFechas,
    tipo_item: str,
    item_id: uuid.UUID,
) -> tuple[list[MovimientoSalida], int]:
    nombre_item(db, ctx, tipo_item, item_id)  # 404 si no existe en la sede
    return movimientos(
        db, ctx, params, rango, tipo_item=tipo_item, item_id=item_id, ascendente=True
    )


def _inicio(dia: date) -> datetime:
    """Medianoche local del día, para filtrar por fecha del negocio."""
    return datetime.combine(dia, time(), tzinfo=zona())


# --- Alertas y resumen ----------------------------------------------------------------------


def alertas(db: Session, ctx: Contexto) -> list[Alerta]:
    dia = hoy()
    salida: list[Alerta] = []
    for item in _items(db, ctx):
        cantidad = item.stock(dia).cantidad
        if item.bajo_minimo(cantidad):
            salida.append(
                Alerta(
                    tipo="bajo_minimo",
                    tipo_item=item.tipo_item,
                    item_id=item.item_id,
                    titulo=f"{item.nombre} está bajo el mínimo",
                    detalle=f"Hay {_num(cantidad)} {item.unidad}; el mínimo es "
                    f"{_num(item.minimo)} {item.unidad}.",
                )
            )
        for lote in item.lotes:
            if item.vencido(lote, dia):
                salida.append(
                    Alerta(
                        tipo="vencido",
                        tipo_item=item.tipo_item,
                        item_id=item.item_id,
                        lote_id=lote.id,
                        titulo=f"{item.nombre}: lote vencido",
                        detalle=f"Venció el {lote.fecha_vencimiento:%d/%m/%Y} y quedan "
                        f"{_num(lote.cantidad_disponible)} {item.unidad}. Regístralo como merma.",
                    )
                )
            elif item.por_vencer(lote, dia):
                dias = (lote.fecha_vencimiento - dia).days
                cuando = {0: "hoy", 1: "mañana"}.get(dias, f"en {dias} días")
                salida.append(
                    Alerta(
                        tipo="por_vencer",
                        tipo_item=item.tipo_item,
                        item_id=item.item_id,
                        lote_id=lote.id,
                        titulo=f"{item.nombre}: un lote vence {cuando}",
                        detalle=f"Quedan {_num(lote.cantidad_disponible)} {item.unidad} "
                        f"que vencen el {lote.fecha_vencimiento:%d/%m/%Y}.",
                    )
                )
    salida.extend(_alertas_faltantes(db, ctx))
    if (verificacion := _alerta_verificacion(db, ctx)) is not None:
        salida.append(verificacion)
    return salida


def _alertas_faltantes(db: Session, ctx: Contexto) -> list[Alerta]:
    filas = db.execute(
        select(
            FaltanteInventario.tipo_item,
            FaltanteInventario.item_id,
            func.sum(FaltanteInventario.cantidad_pendiente),
        )
        .where(FaltanteInventario.sede_id == ctx.sede_id, FaltanteInventario.estado == "abierto")
        .group_by(FaltanteInventario.tipo_item, FaltanteInventario.item_id)
    ).all()
    nombres = nombres_items(db, [_Ref(t, i) for t, i, _ in filas])
    unidades = dict(
        db.execute(
            select(Insumo.id, Insumo.unidad_base).where(
                Insumo.id.in_([i for t, i, _ in filas if t == "insumo"])
            )
        ).all()
    )
    return [
        Alerta(
            tipo="faltante",
            tipo_item=tipo_item,
            item_id=item_id,
            titulo=f"{nombres.get(item_id, 'Ítem')}: faltante por regularizar",
            detalle=f"Se vendieron {_num(pendiente)} {unidades.get(item_id, 'und')} sin stock "
            "registrado. Se descuentan del próximo lote que entre.",
        )
        for tipo_item, item_id, pendiente in filas
    ]


@dataclass
class _Ref:
    tipo_item: str
    item_id: uuid.UUID


def _alerta_verificacion(db: Session, ctx: Contexto) -> Alerta | None:
    ultima = db.scalar(
        select(VerificacionInventario)
        .where(VerificacionInventario.sede_id == ctx.sede_id)
        .order_by(VerificacionInventario.fecha.desc())
        .limit(1)
    )
    if ultima is None or not ultima.diferencias:
        return None
    n = len(ultima.diferencias)
    return Alerta(
        tipo="verificacion",
        titulo=f"La verificación del inventario encontró {n} "
        f"{'diferencia' if n == 1 else 'diferencias'}",
        detalle="Algún lote no cuadra con su libro de movimientos. Revisa el detalle con el "
        "administrador antes de seguir ajustando.",
    )


def resumen(db: Session, ctx: Contexto) -> Kpis:
    dia = hoy()
    items = _items(db, ctx)
    por_vencer = [
        item.nombre for item in items for lote in item.lotes if item.por_vencer(lote, dia)
    ]
    mermas = db.scalar(
        select(func.coalesce(func.sum(Merma.costo_total), 0)).where(
            Merma.sede_id == ctx.sede_id, Merma.fecha >= _inicio(dia.replace(day=1))
        )
    )
    stocks = [item.stock(dia) for item in items]
    return Kpis(
        valor_inventario=sum(s.valor for s in stocks),
        bajo_minimo=[
            item.nombre
            for item, s in zip(items, stocks, strict=True)
            if item.bajo_minimo(s.cantidad)
        ],
        lotes_por_vencer=len(por_vencer),
        por_vencer=por_vencer,
        mermas_mes=int(mermas),
    )
