"""Producción por lote (#21, RF-29, RN-07).

Consume los insumos de la receta vigente × (cantidad / rendimiento) por PEPS y crea un lote del
producto terminado con costo unitario = costo total consumido / unidades producidas.
"""

import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar
from app.modules.auth.models import Usuario
from app.modules.carta.models import Producto, Receta
from app.modules.carta.service import obtener_producto, receta_vigente
from app.modules.inventario import motor
from app.modules.inventario.models import Insumo, Lote, MovimientoInventario
from app.modules.produccion.models import Produccion
from app.modules.produccion.schemas import ConsumoSalida, ProduccionCrear, ProduccionSalida
from app.shared.dinero import ESCALA_CANTIDAD, dividir_costo
from app.shared.errores import Conflicto, ErrorNegocio, NoEncontrado
from app.shared.fechas import ahora, hoy
from app.shared.paginacion import ParamsPagina, RangoFechas, paginar


def cantidades_por_insumo(
    receta: Receta, cantidad_producida: Decimal
) -> list[tuple[uuid.UUID, Decimal]]:
    """Cantidad de cada insumo para producir: receta × (producido / rendimiento), a 4 decimales.
    Ordenadas por insumo para que dos producciones simultáneas bloqueen lotes en el mismo orden."""
    factor = cantidad_producida / receta.rendimiento
    salida = []
    for item in sorted(receta.items, key=lambda i: str(i.insumo_id)):
        cantidad = (item.cantidad * factor).quantize(ESCALA_CANTIDAD, rounding=ROUND_HALF_UP)
        if cantidad > 0:
            salida.append((item.insumo_id, cantidad))
    return salida


def crear(db: Session, ctx: Contexto, datos: ProduccionCrear) -> Produccion:
    producto = obtener_producto(db, ctx, datos.producto_id)
    if producto.tipo != "lote":
        raise ErrorNegocio(
            "PRODUCTO_NO_ES_LOTE",
            "Solo se producen por lote los productos de vitrina; los preparados descuentan su "
            "receta al venderse.",
            status=422,
        )
    receta = receta_vigente(db, producto_id=producto.id)
    if receta is None:
        raise ErrorNegocio(
            "SIN_RECETA", "Este producto no tiene receta: créala antes de producir.", status=422
        )
    responsable_id = datos.responsable_id or ctx.usuario_id
    if db.get(Usuario, responsable_id) is None:
        raise NoEncontrado("el responsable", responsable_id)

    produccion = Produccion(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        producto_id=producto.id,
        receta_id=receta.id,
        cantidad_producida=datos.cantidad_producida,
        costo_total=0,
        responsable_id=responsable_id,
        fecha=ahora(),
    )
    db.add(produccion)
    db.flush()

    costo_total = 0
    for insumo_id, cantidad in cantidades_por_insumo(receta, datos.cantidad_producida):
        try:
            resultado = motor.consumir(
                db,
                ctx,
                tipo_item="insumo",
                item_id=insumo_id,
                cantidad=cantidad,
                tipo_mov="consumo_produccion",
                referencia_tipo="produccion",
                referencia_id=produccion.id,
            )
        except motor.StockInsuficiente as exc:
            exc.detalle["nombre"] = db.get(Insumo, insumo_id).nombre
            exc.mensaje = f"No alcanza {exc.detalle['nombre']} para esta producción."
            raise
        costo_total += resultado.costo_total

    vence = datos.fecha_vencimiento
    if vence is None and producto.dias_vida_util is not None:
        vence = hoy() + timedelta(days=producto.dias_vida_util)
    lote = motor.crear_lote(
        db,
        ctx,
        tipo_item="producto",
        item_id=producto.id,
        origen="produccion",
        origen_id=produccion.id,
        cantidad=datos.cantidad_producida,
        costo_unitario=dividir_costo(costo_total, datos.cantidad_producida),
        tipo_mov="entrada_produccion",
        referencia_tipo="produccion",
        referencia_id=produccion.id,
        vence=vence,
    )
    produccion.costo_total = costo_total
    produccion.lote_resultante_id = lote.id
    db.flush()
    auditar(
        db,
        ctx,
        "crear",
        "producciones",
        produccion.id,
        despues={
            "producto": producto.nombre,
            "cantidad": str(datos.cantidad_producida),
            "costo_total": costo_total,
            "receta_version": receta.version,
        },
    )
    return produccion


def obtener(
    db: Session, ctx: Contexto, produccion_id: uuid.UUID, bloquear: bool = False
) -> Produccion:
    consulta = select(Produccion).where(
        Produccion.id == produccion_id, Produccion.sede_id == ctx.sede_id
    )
    if bloquear:
        consulta = consulta.with_for_update()
    p = db.scalar(consulta)
    if p is None:
        raise NoEncontrado("la producción", produccion_id)
    return p


def anular(db: Session, ctx: Contexto, produccion_id: uuid.UUID, motivo: str) -> Produccion:
    """Solo si el lote producido sigue completo: los insumos vuelven a sus mismos lotes."""
    p = obtener(db, ctx, produccion_id, bloquear=True)
    if p.anulada:
        raise Conflicto("YA_ANULADO", "Esta producción ya se anuló.")
    try:
        motor.reversar(db, ctx, "produccion", p.id)
    except Conflicto as exc:
        if exc.codigo != "LOTE_CONSUMIDO":
            raise
        raise Conflicto(
            "PRODUCCION_CON_SALIDAS",
            "Parte de lo producido ya se vendió o se dio de baja; no se puede anular.",
        ) from exc
    p.anulada = True
    p.anulada_en = ahora()
    p.anulada_por = ctx.usuario_id
    p.motivo_anulacion = motivo
    db.flush()
    auditar(db, ctx, "anular", "producciones", p.id, despues={"motivo": motivo})
    return p


def salida(db: Session, p: Produccion) -> ProduccionSalida:
    producto = db.get(Producto, p.producto_id)
    receta = db.get(Receta, p.receta_id)
    lote = db.get(Lote, p.lote_resultante_id) if p.lote_resultante_id else None
    responsable = db.get(Usuario, p.responsable_id) if p.responsable_id else None
    consumos = db.execute(
        select(
            MovimientoInventario.item_id,
            Insumo.nombre,
            Insumo.unidad_base,
            MovimientoInventario.cantidad,
            MovimientoInventario.costo_total,
        )
        .join(Insumo, Insumo.id == MovimientoInventario.item_id)
        .where(
            MovimientoInventario.referencia_tipo == "produccion",
            MovimientoInventario.referencia_id == p.id,
            MovimientoInventario.tipo == "consumo_produccion",
        )
        .order_by(Insumo.nombre)
    ).all()
    agrupados: dict[uuid.UUID, ConsumoSalida] = {}
    for insumo_id, nombre, unidad, cantidad, costo in consumos:
        c = agrupados.setdefault(
            insumo_id,
            ConsumoSalida(
                insumo_id=insumo_id,
                insumo=nombre,
                unidad=unidad,
                cantidad=Decimal(0),
                costo_total=0,
            ),
        )
        c.cantidad += -cantidad
        c.costo_total += -costo
    return ProduccionSalida(
        id=p.id,
        producto_id=p.producto_id,
        producto=producto.nombre,
        receta_id=p.receta_id,
        receta_version=receta.version,
        cantidad_producida=p.cantidad_producida,
        costo_total=p.costo_total,
        costo_unitario=lote.costo_unitario if lote else Decimal(0),
        fecha_vencimiento=lote.fecha_vencimiento if lote else None,
        lote_resultante_id=p.lote_resultante_id,
        responsable=responsable.nombre if responsable else None,
        fecha=p.fecha,
        anulada=p.anulada,
        motivo_anulacion=p.motivo_anulacion,
        consumos=list(agrupados.values()),
    )


def listar(
    db: Session,
    ctx: Contexto,
    params: ParamsPagina,
    rango: RangoFechas,
    producto_id: uuid.UUID | None,
) -> tuple[list[ProduccionSalida], int]:
    consulta = (
        select(Produccion)
        .where(Produccion.sede_id == ctx.sede_id)
        .order_by(Produccion.fecha.desc())
    )
    if producto_id:
        consulta = consulta.where(Produccion.producto_id == producto_id)
    if rango.desde:
        consulta = consulta.where(Produccion.fecha >= rango.desde)
    if rango.hasta:
        consulta = consulta.where(Produccion.fecha < rango.hasta + timedelta(days=1))
    filas, total = paginar(db, consulta, params)
    return [salida(db, p) for p in filas], total
