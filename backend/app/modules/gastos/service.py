"""Gastos (#34, RF-21 a RF-23). Un gasto de caja sale del arqueo (movimiento `gasto`); uno de
banco o de los dueños queda registrado para los reportes sin tocar la caja."""

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar
from app.modules.auth.models import Usuario
from app.modules.caja import service as caja
from app.modules.configuracion.models import MetodoPago
from app.modules.gastos.models import (
    CATEGORIA_DECORACION,
    CATEGORIAS_INICIALES,
    CategoriaGasto,
    Gasto,
)
from app.modules.gastos.schemas import CategoriaCrear, CategoriaEditar, GastoCrear, GastoSalida
from app.shared.bd import guardar_unico
from app.shared.errores import Conflicto, NoEncontrado, SinPermiso
from app.shared.fechas import ahora, hoy
from app.shared.paginacion import ParamsPagina, RangoFechas, paginar

DUPLICADA = "Ya existe una categoría de gasto con ese nombre."


def sembrar_categorias(db: Session, sede_id: uuid.UUID) -> None:
    """Categorías iniciales para una sede nueva."""
    for nombre, puc in (*CATEGORIAS_INICIALES, CATEGORIA_DECORACION):
        db.add(CategoriaGasto(sede_id=sede_id, nombre=nombre, cuenta_puc=puc))


def listar_categorias(db: Session, ctx: Contexto, incluir_inactivas: bool) -> list[CategoriaGasto]:
    consulta = select(CategoriaGasto).where(CategoriaGasto.sede_id == ctx.sede_id)
    if not incluir_inactivas:
        consulta = consulta.where(CategoriaGasto.activa)
    return list(db.scalars(consulta.order_by(CategoriaGasto.nombre)))


def _categoria(db: Session, ctx: Contexto, categoria_id: uuid.UUID) -> CategoriaGasto:
    c = db.get(CategoriaGasto, categoria_id)
    if c is None or c.sede_id != ctx.sede_id:
        raise NoEncontrado("la categoría de gasto", categoria_id)
    return c


def crear_categoria(db: Session, ctx: Contexto, datos: CategoriaCrear) -> CategoriaGasto:
    c = CategoriaGasto(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        nombre=datos.nombre.strip(),
        cuenta_puc=datos.cuenta_puc,
    )
    db.add(c)
    guardar_unico(db, mensaje=DUPLICADA)
    auditar(db, ctx, "crear", "categorias_gasto", c.id, despues=datos.model_dump())
    return c


def editar_categoria(
    db: Session, ctx: Contexto, categoria_id: uuid.UUID, datos: CategoriaEditar
) -> CategoriaGasto:
    c = _categoria(db, ctx, categoria_id)
    cambios = datos.model_dump(exclude_unset=True)
    renombra = "nombre" in cambios and cambios["nombre"] != c.nombre
    if c.sistema and (renombra or cambios.get("activa") is False):
        raise Conflicto(
            "CATEGORIA_DEL_SISTEMA",
            "Esta categoría la usan los gastos de decoración de los encargos: "
            "no se puede renombrar ni desactivar.",
        )
    for campo, valor in cambios.items():
        setattr(c, campo, valor)
    guardar_unico(db, mensaje=DUPLICADA)
    auditar(db, ctx, "editar", "categorias_gasto", c.id, despues=cambios)
    return c


def categoria_decoracion(db: Session, ctx: Contexto) -> CategoriaGasto:
    """La categoría de los materiales de decoración de encargos; si no está, se crea."""
    nombre, puc = CATEGORIA_DECORACION
    categoria = db.scalar(
        select(CategoriaGasto).where(
            CategoriaGasto.sede_id == ctx.sede_id, CategoriaGasto.nombre == nombre
        )
    )
    if categoria is None:
        categoria = CategoriaGasto(
            id=uuid.uuid4(), sede_id=ctx.sede_id, nombre=nombre, cuenta_puc=puc
        )
        db.add(categoria)
        db.flush()
    return categoria


def crear(
    db: Session, ctx: Contexto, datos: GastoCrear, encargo_id: uuid.UUID | None = None
) -> Gasto:
    # Quien solo tiene gastos.crear_caja (cajero) registra únicamente gastos pagados de la caja.
    if datos.fuente != "caja" and "gastos.crear" not in ctx.permisos:
        raise SinPermiso("gastos.crear")
    categoria = _categoria(db, ctx, datos.categoria_id)
    if not categoria.activa:
        raise Conflicto("CATEGORIA_INACTIVA", "Esa categoría de gasto está inactiva.")
    metodo = db.get(MetodoPago, datos.metodo_pago_id)
    if metodo is None or metodo.sede_id != ctx.sede_id:
        raise NoEncontrado("el método de pago", datos.metodo_pago_id)
    gasto = Gasto(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        fecha=datos.fecha or hoy(),
        categoria_id=categoria.id,
        descripcion=datos.descripcion.strip(),
        monto=datos.monto,
        metodo_pago_id=metodo.id,
        fuente=datos.fuente,
        proveedor_id=datos.proveedor_id,
        encargo_id=encargo_id,
        soporte_url=datos.soporte_url,
        usuario_id=ctx.usuario_id,
    )
    if datos.fuente == "caja":
        mov = caja.registrar_movimiento(
            db,
            ctx,
            tipo="gasto",
            metodo_pago_id=metodo.id,
            monto=-datos.monto,
            referencia_tipo="gasto",
            referencia_id=gasto.id,
            motivo=gasto.descripcion,
        )
        gasto.caja_sesion_id = mov.caja_sesion_id
    db.add(gasto)
    db.flush()
    auditar(
        db, ctx, "crear", "gastos", gasto.id, despues={"monto": gasto.monto, "fuente": gasto.fuente}
    )
    return gasto


def anular(db: Session, ctx: Contexto, gasto_id: uuid.UUID, motivo: str) -> Gasto:
    gasto = db.get(Gasto, gasto_id, with_for_update=True)
    if gasto is None or gasto.sede_id != ctx.sede_id:
        raise NoEncontrado("el gasto", gasto_id)
    if gasto.estado == "anulado":
        raise Conflicto("YA_ANULADO", "Este gasto ya se anuló.")
    if gasto.fuente == "caja":
        # RN-03: el dinero vuelve a la caja abierta hoy.
        caja.reversar(db, ctx, "gasto", gasto.id, f"Anulación de gasto: {motivo}")
    gasto.estado = "anulado"
    gasto.motivo_anulacion = motivo
    gasto.anulado_por = ctx.usuario_id
    gasto.anulado_en = ahora()
    db.flush()
    auditar(db, ctx, "anular", "gastos", gasto.id, despues={"motivo": motivo})
    return gasto


def salida(db: Session, g: Gasto) -> GastoSalida:
    s = GastoSalida.model_validate(g, from_attributes=True)
    cat = db.get(CategoriaGasto, g.categoria_id)
    s.categoria, s.cuenta_puc = cat.nombre, cat.cuenta_puc
    s.metodo = db.scalar(select(MetodoPago.nombre).where(MetodoPago.id == g.metodo_pago_id))
    s.usuario = db.scalar(select(Usuario.nombre).where(Usuario.id == g.usuario_id))
    s.encargo_numero = g.encargo.numero if g.encargo else None
    return s


def listar(
    db: Session,
    ctx: Contexto,
    params: ParamsPagina,
    rango: RangoFechas,
    fuente: str | None,
    categoria_id: uuid.UUID | None,
    estado: str | None,
) -> tuple[list[GastoSalida], int]:
    consulta = (
        select(Gasto)
        .where(Gasto.sede_id == ctx.sede_id)
        .order_by(Gasto.fecha.desc(), Gasto.creado_en.desc())
    )
    # Quien solo registra gastos de caja (cajero) ve los suyos.
    if "gastos.crear" not in ctx.permisos and "reportes.ver" not in ctx.permisos:
        consulta = consulta.where(Gasto.usuario_id == ctx.usuario_id)
    if fuente:
        consulta = consulta.where(Gasto.fuente == fuente)
    if categoria_id:
        consulta = consulta.where(Gasto.categoria_id == categoria_id)
    if estado:
        consulta = consulta.where(Gasto.estado == estado)
    if rango.desde:
        consulta = consulta.where(Gasto.fecha >= rango.desde)
    if rango.hasta:
        consulta = consulta.where(Gasto.fecha < rango.hasta + timedelta(days=1))
    filas, total = paginar(db, consulta, params)
    return [salida(db, g) for g in filas], total
