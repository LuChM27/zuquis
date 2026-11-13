"""Mermas y ajustes por conteo físico (#22, RF-30, RF-31, RN-10, RN-11).

La merma consume por PEPS (o del lote indicado) y su costo se reporta como gasto aparte, no
dentro del costo de ventas. Se pueden dar de baja lotes vencidos (RN-11).

El ajuste compara lo contado con el sistema: si falta, consume PEPS; si sobra, crea un lote de
origen ``ajuste`` al costo del último lote del ítem (RN-10).
"""

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar
from app.modules.carta.models import Producto
from app.modules.carta.service import obtener_producto
from app.modules.inventario import motor
from app.modules.inventario.models import AjusteInventario, Insumo, Lote, Merma
from app.modules.inventario.schemas import AjusteCrear, AjusteSalida, MermaCrear, MermaSalida
from app.modules.inventario.service import obtener_insumo
from app.shared.dinero import costo_linea
from app.shared.errores import ErrorNegocio, NoEncontrado
from app.shared.fechas import ahora
from app.shared.paginacion import ParamsPagina, RangoFechas, paginar


def nombre_item(db: Session, ctx: Contexto, tipo_item: str, item_id: uuid.UUID) -> str:
    """Valida que el ítem exista en la sede y devuelve su nombre."""
    if tipo_item == "insumo":
        return obtener_insumo(db, ctx, item_id).nombre
    return obtener_producto(db, ctx, item_id).nombre


def nombres_items(db: Session, filas) -> dict[uuid.UUID, str]:
    ids_insumos = {f.item_id for f in filas if f.tipo_item == "insumo"}
    ids_productos = {f.item_id for f in filas if f.tipo_item == "producto"}
    nombres: dict[uuid.UUID, str] = {}
    if ids_insumos:
        nombres.update(
            db.execute(select(Insumo.id, Insumo.nombre).where(Insumo.id.in_(ids_insumos))).all()
        )
    if ids_productos:
        nombres.update(
            db.execute(
                select(Producto.id, Producto.nombre).where(Producto.id.in_(ids_productos))
            ).all()
        )
    return nombres


def _con_nombre_en_error(exc: motor.StockInsuficiente, nombre: str, mensaje: str) -> None:
    exc.detalle["nombre"] = nombre
    exc.mensaje = mensaje


# --- Mermas ---------------------------------------------------------------------------------


def registrar_merma(db: Session, ctx: Contexto, datos: MermaCrear) -> Merma:
    nombre = nombre_item(db, ctx, datos.tipo_item, datos.item_id)
    if datos.lote_id is not None:
        lote = db.get(Lote, datos.lote_id)
        if (
            lote is None
            or lote.sede_id != ctx.sede_id
            or lote.tipo_item != datos.tipo_item
            or lote.item_id != datos.item_id
        ):
            raise NoEncontrado("el lote", datos.lote_id)

    merma = Merma(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        tipo_item=datos.tipo_item,
        item_id=datos.item_id,
        lote_id=datos.lote_id,
        cantidad=datos.cantidad,
        motivo=datos.motivo,
        nota=datos.nota,
        costo_total=0,
        usuario_id=ctx.usuario_id,
        fecha=ahora(),
    )
    db.add(merma)
    db.flush()
    try:
        resultado = motor.consumir(
            db,
            ctx,
            tipo_item=datos.tipo_item,
            item_id=datos.item_id,
            cantidad=datos.cantidad,
            tipo_mov="merma",
            referencia_tipo="merma",
            referencia_id=merma.id,
            incluir_vencidos=True,  # RN-11: lo vencido solo sale como merma
            lote_id=datos.lote_id,
        )
    except motor.StockInsuficiente as exc:
        donde = "en ese lote" if datos.lote_id else "en inventario"
        _con_nombre_en_error(exc, nombre, f"No hay tanto {nombre} {donde} para dar de baja.")
        raise
    merma.costo_total = resultado.costo_total
    if merma.lote_id is None and len(resultado.consumos) == 1:
        merma.lote_id = resultado.consumos[0].lote_id
    db.flush()
    auditar(
        db,
        ctx,
        "crear",
        "mermas",
        merma.id,
        despues={
            "item": nombre,
            "cantidad": str(datos.cantidad),
            "motivo": datos.motivo,
            "costo_total": merma.costo_total,
        },
    )
    return merma


def merma_salida(merma: Merma, nombre: str | None) -> MermaSalida:
    return MermaSalida(
        id=merma.id,
        tipo_item=merma.tipo_item,
        item_id=merma.item_id,
        item_nombre=nombre,
        lote_id=merma.lote_id,
        cantidad=merma.cantidad,
        motivo=merma.motivo,
        nota=merma.nota,
        costo_total=merma.costo_total,
        fecha=merma.fecha,
    )


def listar_mermas(
    db: Session,
    ctx: Contexto,
    params: ParamsPagina,
    rango: RangoFechas,
    tipo_item: str | None,
    item_id: uuid.UUID | None,
    motivo: str | None,
) -> tuple[list[MermaSalida], int]:
    consulta = select(Merma).where(Merma.sede_id == ctx.sede_id).order_by(Merma.fecha.desc())
    if tipo_item:
        consulta = consulta.where(Merma.tipo_item == tipo_item)
    if item_id:
        consulta = consulta.where(Merma.item_id == item_id)
    if motivo:
        consulta = consulta.where(Merma.motivo == motivo)
    if rango.desde:
        consulta = consulta.where(Merma.fecha >= rango.desde)
    if rango.hasta:
        consulta = consulta.where(Merma.fecha < rango.hasta + timedelta(days=1))
    filas, total = paginar(db, consulta, params)
    nombres = nombres_items(db, filas)
    return [merma_salida(m, nombres.get(m.item_id)) for m in filas], total


# --- Ajustes por conteo físico --------------------------------------------------------------


def registrar_ajuste(db: Session, ctx: Contexto, datos: AjusteCrear) -> AjusteInventario:
    nombre = nombre_item(db, ctx, datos.tipo_item, datos.item_id)
    # Se bloquean los lotes antes de leer el stock: así nadie consume entre la lectura y el
    # ajuste, y la diferencia se calcula sobre lo que de verdad hay.
    db.scalars(
        select(Lote.id)
        .where(
            Lote.sede_id == ctx.sede_id,
            Lote.tipo_item == datos.tipo_item,
            Lote.item_id == datos.item_id,
        )
        .with_for_update()
    ).all()
    # Se cuenta solo lo vigente. Lo vencido se informa aparte para darlo de baja como merma.
    sistema = motor.stock(db, ctx.sede_id, datos.tipo_item, datos.item_id, incluir_vencidos=False)
    vencida = (
        motor.stock(db, ctx.sede_id, datos.tipo_item, datos.item_id, incluir_vencidos=True)
        - sistema
    )
    diferencia = datos.cantidad_contada - sistema
    if diferencia == 0:
        raise ErrorNegocio(
            "SIN_DIFERENCIA",
            f"El conteo de {nombre} coincide con el sistema: no hay nada que ajustar.",
            status=422,
        )

    ajuste = AjusteInventario(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        tipo_item=datos.tipo_item,
        item_id=datos.item_id,
        cantidad_sistema=sistema,
        cantidad_contada=datos.cantidad_contada,
        diferencia=diferencia,
        cantidad_vencida=vencida,
        costo_total=0,
        motivo=datos.motivo,
        aprobado_por=ctx.usuario_id,
        fecha=ahora(),
    )
    db.add(ajuste)
    db.flush()

    if diferencia < 0:
        resultado = motor.consumir(
            db,
            ctx,
            tipo_item=datos.tipo_item,
            item_id=datos.item_id,
            cantidad=-diferencia,
            tipo_mov="ajuste",
            referencia_tipo="ajuste",
            referencia_id=ajuste.id,
        )
        ajuste.costo_total = -resultado.costo_total
    else:
        lote = motor.ajuste_positivo(
            db,
            ctx,
            tipo_item=datos.tipo_item,
            item_id=datos.item_id,
            cantidad=diferencia,
            referencia_id=ajuste.id,
            costo_unitario=datos.costo_unitario,
        )
        ajuste.costo_total = costo_linea(diferencia, lote.costo_unitario)
    db.flush()
    auditar(
        db,
        ctx,
        "crear",
        "ajustes_inventario",
        ajuste.id,
        antes={"cantidad": str(sistema)},
        despues={
            "item": nombre,
            "cantidad": str(datos.cantidad_contada),
            "diferencia": str(diferencia),
            "cantidad_vencida": str(vencida),
            "costo_total": ajuste.costo_total,
            "motivo": datos.motivo,
        },
    )
    return ajuste


def ajuste_salida(ajuste: AjusteInventario) -> AjusteSalida:
    return AjusteSalida.model_validate(ajuste, from_attributes=True)


def listar_ajustes(
    db: Session,
    ctx: Contexto,
    params: ParamsPagina,
    rango: RangoFechas,
    item_id: uuid.UUID | None,
) -> tuple[list[AjusteSalida], int]:
    consulta = (
        select(AjusteInventario)
        .where(AjusteInventario.sede_id == ctx.sede_id)
        .order_by(AjusteInventario.fecha.desc())
    )
    if item_id:
        consulta = consulta.where(AjusteInventario.item_id == item_id)
    if rango.desde:
        consulta = consulta.where(AjusteInventario.fecha >= rango.desde)
    if rango.hasta:
        consulta = consulta.where(AjusteInventario.fecha < rango.hasta + timedelta(days=1))
    filas, total = paginar(db, consulta, params)
    return [ajuste_salida(a) for a in filas], total
