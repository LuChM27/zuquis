"""Insumos, presentaciones y conversión de unidades (#17)."""

import uuid
from decimal import Decimal

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar, instantanea
from app.modules.configuracion.models import Unidad
from app.modules.inventario.models import Insumo, MovimientoInventario, Presentacion
from app.modules.inventario.schemas import (
    InsumoCrear,
    InsumoEditar,
    PresentacionCrear,
    PresentacionEditar,
)
from app.shared.bd import guardar_unico
from app.shared.dinero import ESCALA_CANTIDAD, a_decimal
from app.shared.errores import Conflicto, ErrorNegocio, NoEncontrado

CAMPOS_INSUMO = ["nombre", "unidad_base", "stock_minimo", "dias_alerta_vencimiento", "activo"]


def convertir(cantidad: Decimal, presentacion: Presentacion | None) -> Decimal:
    """Cantidad en la presentación → unidad base del insumo (0,5 Litro → 500 ml)."""
    factor = presentacion.factor if presentacion else Decimal(1)
    resultado = a_decimal(cantidad) * factor
    if resultado != resultado.quantize(ESCALA_CANTIDAD):
        raise ErrorNegocio(
            "VALIDACION",
            "La conversión da más de 4 decimales en la unidad base; revisa la cantidad.",
            status=422,
        )
    return resultado.quantize(ESCALA_CANTIDAD)


def obtener_insumo(db: Session, ctx: Contexto, insumo_id: uuid.UUID) -> Insumo:
    insumo = db.get(Insumo, insumo_id)
    if insumo is None or insumo.sede_id != ctx.sede_id:
        raise NoEncontrado("el insumo", insumo_id)
    return insumo


def obtener_presentacion(
    db: Session, ctx: Contexto, insumo_id: uuid.UUID, presentacion_id: uuid.UUID
) -> Presentacion:
    p = db.get(Presentacion, presentacion_id)
    if p is None or p.insumo_id != insumo_id or p.sede_id != ctx.sede_id:
        raise NoEncontrado("la presentación", presentacion_id)
    return p


def _validar_unidad(db: Session, codigo: str) -> None:
    if db.scalar(select(Unidad).where(Unidad.codigo == codigo)) is None:
        raise ErrorNegocio(
            "UNIDAD_DESCONOCIDA", "La unidad base debe ser g, ml o und.", {"unidad": codigo}, 422
        )


def listar_insumos(db: Session, ctx: Contexto, incluir_inactivos: bool = False) -> list[Insumo]:
    consulta = (
        select(Insumo)
        .where(Insumo.sede_id == ctx.sede_id)
        .options(selectinload(Insumo.presentaciones))
        .order_by(Insumo.nombre)
    )
    if not incluir_inactivos:
        consulta = consulta.where(Insumo.activo)
    return list(db.scalars(consulta))


def crear_insumo(db: Session, ctx: Contexto, datos: InsumoCrear) -> Insumo:
    _validar_unidad(db, datos.unidad_base)
    insumo = Insumo(
        sede_id=ctx.sede_id,
        nombre=datos.nombre.strip(),
        unidad_base=datos.unidad_base,
        stock_minimo=datos.stock_minimo,
        dias_alerta_vencimiento=datos.dias_alerta_vencimiento,
    )
    db.add(insumo)
    guardar_unico(db)
    for p in datos.presentaciones:
        db.add(
            Presentacion(
                sede_id=ctx.sede_id, insumo_id=insumo.id, nombre=p.nombre.strip(), factor=p.factor
            )
        )
    guardar_unico(db)
    db.refresh(insumo)
    auditar(db, ctx, "crear", "insumos", insumo.id, despues=instantanea(insumo, CAMPOS_INSUMO))
    return insumo


def tiene_movimientos(db: Session, tipo_item: str, item_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(
            select(
                exists().where(
                    MovimientoInventario.tipo_item == tipo_item,
                    MovimientoInventario.item_id == item_id,
                )
            )
        )
    )


def editar_insumo(db: Session, ctx: Contexto, insumo_id: uuid.UUID, datos: InsumoEditar) -> Insumo:
    insumo = obtener_insumo(db, ctx, insumo_id)
    antes = instantanea(insumo, CAMPOS_INSUMO)
    cambios = datos.model_dump(exclude_unset=True)
    nueva_unidad = cambios.get("unidad_base")
    if nueva_unidad is not None and nueva_unidad != insumo.unidad_base:
        _validar_unidad(db, nueva_unidad)
        if tiene_movimientos(db, "insumo", insumo.id):
            raise Conflicto(
                "UNIDAD_CON_MOVIMIENTOS",
                "No se puede cambiar la unidad base de un insumo que ya tiene movimientos: "
                "las cantidades guardadas quedarían en otra unidad.",
            )
    for campo, valor in cambios.items():
        setattr(
            insumo, campo, valor.strip() if isinstance(valor, str) and campo == "nombre" else valor
        )
    guardar_unico(db)
    auditar(
        db,
        ctx,
        "editar",
        "insumos",
        insumo.id,
        antes=antes,
        despues=instantanea(insumo, CAMPOS_INSUMO),
    )
    return insumo


def crear_presentacion(
    db: Session, ctx: Contexto, insumo_id: uuid.UUID, datos: PresentacionCrear
) -> Presentacion:
    insumo = obtener_insumo(db, ctx, insumo_id)
    p = Presentacion(
        sede_id=ctx.sede_id, insumo_id=insumo.id, nombre=datos.nombre.strip(), factor=datos.factor
    )
    db.add(p)
    guardar_unico(db)
    auditar(
        db,
        ctx,
        "crear",
        "presentaciones",
        p.id,
        despues=instantanea(p, ["insumo_id", "nombre", "factor"]),
    )
    return p


def editar_presentacion(
    db: Session,
    ctx: Contexto,
    insumo_id: uuid.UUID,
    presentacion_id: uuid.UUID,
    datos: PresentacionEditar,
) -> Presentacion:
    p = obtener_presentacion(db, ctx, insumo_id, presentacion_id)
    antes = instantanea(p, ["nombre", "factor", "activa"])
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(p, campo, valor)
    guardar_unico(db)
    auditar(
        db,
        ctx,
        "editar",
        "presentaciones",
        p.id,
        antes=antes,
        despues=instantanea(p, ["nombre", "factor", "activa"]),
    )
    return p
