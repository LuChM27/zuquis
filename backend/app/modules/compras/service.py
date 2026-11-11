"""Proveedores y compras con lotes y cuentas por pagar (#19)."""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar, instantanea
from app.modules.compras.models import Compra, CompraItem, PagoCompra, Proveedor
from app.modules.compras.schemas import (
    CompraCrear,
    CompraItemSalida,
    CompraSalida,
    CuentaPorPagar,
    InsumoResumen,
    PagoEntrada,
    PagoSalida,
    ProveedorCrear,
    ProveedorEditar,
    ProveedorSalida,
)
from app.modules.configuracion.models import MetodoPago
from app.modules.inventario import motor
from app.modules.inventario.models import Insumo, Presentacion
from app.modules.inventario.service import convertir
from app.shared.dinero import dividir_costo, sumar_pesos
from app.shared.errores import Conflicto, ErrorNegocio, NoEncontrado
from app.shared.fechas import ahora, hoy
from app.shared.paginacion import ParamsPagina, RangoFechas, paginar

CAMPOS_PROVEEDOR = ["nombre", "nit_o_cedula", "telefono", "email", "activo"]


# --- Proveedores ----------------------------------------------------------------------------


def _insumos_de(db: Session, ctx: Contexto, ids: list[uuid.UUID]) -> list[Insumo]:
    insumos = list(
        db.scalars(select(Insumo).where(Insumo.id.in_(ids), Insumo.sede_id == ctx.sede_id))
    )
    if len(insumos) != len(set(ids)):
        raise ErrorNegocio("VALIDACION", "Hay insumos que no existen.", status=422)
    return insumos


def proveedor_salida(p: Proveedor) -> ProveedorSalida:
    return ProveedorSalida(
        id=p.id,
        nombre=p.nombre,
        nit_o_cedula=p.nit_o_cedula,
        telefono=p.telefono,
        email=p.email,
        activo=p.activo,
        insumos=[InsumoResumen(id=i.id, nombre=i.nombre) for i in p.insumos],
    )


def obtener_proveedor(db: Session, ctx: Contexto, proveedor_id: uuid.UUID) -> Proveedor:
    p = db.get(Proveedor, proveedor_id)
    if p is None or p.sede_id != ctx.sede_id:
        raise NoEncontrado("el proveedor", proveedor_id)
    return p


def listar_proveedores(db: Session, ctx: Contexto, incluir_inactivos: bool) -> list[Proveedor]:
    consulta = (
        select(Proveedor)
        .where(Proveedor.sede_id == ctx.sede_id)
        .options(selectinload(Proveedor.insumos))
        .order_by(Proveedor.nombre)
    )
    if not incluir_inactivos:
        consulta = consulta.where(Proveedor.activo)
    return list(db.scalars(consulta))


def crear_proveedor(db: Session, ctx: Contexto, datos: ProveedorCrear) -> Proveedor:
    p = Proveedor(sede_id=ctx.sede_id, **datos.model_dump(exclude={"insumo_ids"}))
    p.insumos = _insumos_de(db, ctx, datos.insumo_ids)
    db.add(p)
    db.flush()
    auditar(db, ctx, "crear", "proveedores", p.id, despues=instantanea(p, CAMPOS_PROVEEDOR))
    return p


def editar_proveedor(
    db: Session, ctx: Contexto, proveedor_id: uuid.UUID, datos: ProveedorEditar
) -> Proveedor:
    p = obtener_proveedor(db, ctx, proveedor_id)
    antes = instantanea(p, CAMPOS_PROVEEDOR)
    cambios = datos.model_dump(exclude_unset=True)
    if "insumo_ids" in cambios:
        p.insumos = _insumos_de(db, ctx, cambios.pop("insumo_ids"))
    for campo, valor in cambios.items():
        setattr(p, campo, valor)
    db.flush()
    auditar(
        db,
        ctx,
        "editar",
        "proveedores",
        p.id,
        antes=antes,
        despues=instantanea(p, CAMPOS_PROVEEDOR),
    )
    return p


# --- Compras --------------------------------------------------------------------------------


def _metodo(db: Session, ctx: Contexto, metodo_id: uuid.UUID) -> MetodoPago:
    m = db.get(MetodoPago, metodo_id)
    if m is None or m.sede_id != ctx.sede_id or not m.activo:
        raise NoEncontrado("el método de pago", metodo_id)
    return m


def obtener_compra(
    db: Session, ctx: Contexto, compra_id: uuid.UUID, bloquear: bool = False
) -> Compra:
    consulta = select(Compra).where(Compra.id == compra_id, Compra.sede_id == ctx.sede_id)
    if bloquear:
        consulta = consulta.with_for_update()
    compra = db.scalar(consulta.options(selectinload(Compra.items), selectinload(Compra.pagos)))
    if compra is None:
        raise NoEncontrado("la compra", compra_id)
    return compra


def crear_compra(db: Session, ctx: Contexto, datos: CompraCrear) -> Compra:
    """Una transacción: cada línea convierte a unidad base, calcula su costo unitario y crea
    su lote. Si una línea falla, no queda nada registrado."""
    if datos.proveedor_id:
        obtener_proveedor(db, ctx, datos.proveedor_id)
    metodo = _metodo(db, ctx, datos.metodo_pago_id) if datos.estado_pago == "contado" else None
    compra = Compra(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        proveedor_id=datos.proveedor_id,
        fecha=datos.fecha or hoy(),
        numero_factura_proveedor=datos.numero_factura_proveedor,
        soporte_url=datos.soporte_url,
        estado_pago=datos.estado_pago,
        total=sumar_pesos([i.costo_total for i in datos.items]),
    )
    db.add(compra)
    db.flush()
    for orden, linea in enumerate(datos.items):
        insumo = db.get(Insumo, linea.insumo_id)
        if insumo is None or insumo.sede_id != ctx.sede_id or not insumo.activo:
            raise NoEncontrado("el insumo", linea.insumo_id)
        presentacion = None
        if linea.presentacion_id:
            presentacion = db.get(Presentacion, linea.presentacion_id)
            if (
                presentacion is None
                or presentacion.insumo_id != insumo.id
                or not presentacion.activa
            ):
                raise NoEncontrado("la presentación", linea.presentacion_id)
        cantidad_base = convertir(linea.cantidad, presentacion)
        costo_unitario = dividir_costo(linea.costo_total, cantidad_base)
        lote = motor.crear_lote(
            db,
            ctx,
            tipo_item="insumo",
            item_id=insumo.id,
            origen="compra",
            origen_id=compra.id,
            cantidad=cantidad_base,
            costo_unitario=costo_unitario,
            tipo_mov="compra",
            referencia_tipo="compra",
            referencia_id=compra.id,
            vence=linea.fecha_vencimiento,
        )
        db.add(
            CompraItem(
                sede_id=ctx.sede_id,
                compra_id=compra.id,
                insumo_id=insumo.id,
                presentacion_id=presentacion.id if presentacion else None,
                cantidad=linea.cantidad,
                cantidad_base=cantidad_base,
                costo_total=linea.costo_total,
                costo_unitario=costo_unitario,
                fecha_vencimiento=linea.fecha_vencimiento,
                lote_id=lote.id,
                orden=orden,
            )
        )
    if metodo and compra.total > 0:
        db.add(
            PagoCompra(
                sede_id=ctx.sede_id,
                compra_id=compra.id,
                monto=compra.total,
                metodo_pago_id=metodo.id,
                fecha=ahora(),
            )
        )
    db.flush()
    auditar(
        db,
        ctx,
        "crear",
        "compras",
        compra.id,
        despues={
            "total": compra.total,
            "estado_pago": compra.estado_pago,
            "lineas": len(datos.items),
        },
    )
    return compra


def _pagado(compra: Compra) -> int:
    return sumar_pesos([p.monto for p in compra.pagos])


def registrar_pago(db: Session, ctx: Contexto, compra_id: uuid.UUID, datos: PagoEntrada) -> Compra:
    compra = obtener_compra(db, ctx, compra_id, bloquear=True)
    if compra.anulada:
        raise Conflicto("COMPRA_ANULADA", "La compra está anulada.")
    if compra.estado_pago != "por_pagar":
        raise Conflicto("COMPRA_PAGADA", "Esta compra ya está pagada.")
    _metodo(db, ctx, datos.metodo_pago_id)
    saldo = compra.total - _pagado(compra)
    if datos.monto > saldo:
        raise ErrorNegocio(
            "PAGO_EXCEDE_SALDO",
            "El pago es mayor que lo que se debe de esta compra.",
            {"saldo": saldo},
            status=422,
        )
    pago = PagoCompra(
        sede_id=ctx.sede_id,
        compra_id=compra.id,
        monto=datos.monto,
        metodo_pago_id=datos.metodo_pago_id,
        fecha=ahora(),
    )
    db.add(pago)
    compra.pagos.append(pago)
    if datos.monto == saldo:
        compra.estado_pago = "pagada"
    db.flush()
    auditar(
        db,
        ctx,
        "pagar",
        "compras",
        compra.id,
        despues={"monto": datos.monto, "saldo": saldo - datos.monto},
    )
    return compra


def anular_compra(db: Session, ctx: Contexto, compra_id: uuid.UUID, motivo: str) -> Compra:
    compra = obtener_compra(db, ctx, compra_id, bloquear=True)
    if compra.anulada:
        raise Conflicto("YA_ANULADO", "Esta compra ya se anuló.")
    try:
        motor.reversar(db, ctx, "compra", compra.id)
    except Conflicto as exc:
        if exc.codigo != "LOTE_CONSUMIDO":
            raise
        raise Conflicto(
            "COMPRA_CON_CONSUMOS",
            "Parte de esta compra ya se usó o se vendió, así que no se puede anular. "
            "Si hubo un error en la cantidad, registra un ajuste de inventario.",
            exc.detalle,
        ) from exc
    compra.anulada = True
    compra.anulada_en = ahora()
    compra.anulada_por = ctx.usuario_id
    compra.motivo_anulacion = motivo
    db.flush()
    auditar(db, ctx, "anular", "compras", compra.id, despues={"motivo": motivo})
    return compra


def compra_salida(db: Session, compra: Compra) -> CompraSalida:
    insumos = {
        i.id: i
        for i in db.scalars(
            select(Insumo).where(Insumo.id.in_([x.insumo_id for x in compra.items]))
        )
    }
    presentaciones = {
        p.id: p.nombre
        for p in db.scalars(
            select(Presentacion).where(
                Presentacion.id.in_([x.presentacion_id for x in compra.items if x.presentacion_id])
            )
        )
    }
    metodos = {
        m.id: m.nombre
        for m in db.scalars(
            select(MetodoPago).where(MetodoPago.id.in_([p.metodo_pago_id for p in compra.pagos]))
        )
    }
    proveedor = db.get(Proveedor, compra.proveedor_id) if compra.proveedor_id else None
    pagado = _pagado(compra)
    return CompraSalida(
        id=compra.id,
        proveedor_id=compra.proveedor_id,
        proveedor=proveedor.nombre if proveedor else None,
        fecha=compra.fecha,
        numero_factura_proveedor=compra.numero_factura_proveedor,
        total=compra.total,
        pagado=pagado,
        saldo=compra.total - pagado,
        estado_pago=compra.estado_pago,
        soporte_url=compra.soporte_url,
        anulada=compra.anulada,
        motivo_anulacion=compra.motivo_anulacion,
        creado_en=compra.creado_en,
        items=[
            CompraItemSalida(
                id=x.id,
                insumo_id=x.insumo_id,
                insumo=insumos[x.insumo_id].nombre,
                unidad=insumos[x.insumo_id].unidad_base,
                presentacion=presentaciones.get(x.presentacion_id),
                cantidad=x.cantidad,
                cantidad_base=x.cantidad_base,
                costo_total=x.costo_total,
                costo_unitario=x.costo_unitario,
                fecha_vencimiento=x.fecha_vencimiento,
                lote_id=x.lote_id,
            )
            for x in compra.items
        ],
        pagos=[
            PagoSalida(
                id=p.id,
                fecha=p.fecha,
                monto=p.monto,
                metodo_pago_id=p.metodo_pago_id,
                metodo_pago=metodos.get(p.metodo_pago_id),
            )
            for p in compra.pagos
        ],
    )


def listar_compras(
    db: Session,
    ctx: Contexto,
    params: ParamsPagina,
    rango: RangoFechas,
    proveedor_id: uuid.UUID | None,
    estado_pago: str | None,
) -> tuple[list[CompraSalida], int]:
    consulta = (
        select(Compra)
        .where(Compra.sede_id == ctx.sede_id)
        .options(selectinload(Compra.items), selectinload(Compra.pagos))
        .order_by(Compra.fecha.desc(), Compra.creado_en.desc())
    )
    if rango.desde:
        consulta = consulta.where(Compra.fecha >= rango.desde)
    if rango.hasta:
        consulta = consulta.where(Compra.fecha <= rango.hasta)
    if proveedor_id:
        consulta = consulta.where(Compra.proveedor_id == proveedor_id)
    if estado_pago:
        consulta = consulta.where(Compra.estado_pago == estado_pago)
    compras, total = paginar(db, consulta, params)
    return [compra_salida(db, c) for c in compras], total


def cuentas_por_pagar(db: Session, ctx: Contexto) -> list[CuentaPorPagar]:
    pagos = (
        select(PagoCompra.compra_id, func.sum(PagoCompra.monto).label("pagado"))
        .group_by(PagoCompra.compra_id)
        .subquery()
    )
    saldo = Compra.total - func.coalesce(pagos.c.pagado, 0)
    filas = db.execute(
        select(
            Compra.proveedor_id,
            Proveedor.nombre,
            func.count(Compra.id),
            func.sum(saldo),
            func.min(Compra.fecha),
        )
        .outerjoin(pagos, pagos.c.compra_id == Compra.id)
        .outerjoin(Proveedor, Proveedor.id == Compra.proveedor_id)
        .where(Compra.sede_id == ctx.sede_id, Compra.estado_pago == "por_pagar", ~Compra.anulada)
        .group_by(Compra.proveedor_id, Proveedor.nombre)
        .order_by(func.sum(saldo).desc())
    ).all()
    return [
        CuentaPorPagar(
            proveedor_id=proveedor_id,
            proveedor=nombre or "Sin proveedor",
            compras=compras,
            saldo=int(total_saldo),
            mas_antigua=mas_antigua if isinstance(mas_antigua, date) else hoy(),
        )
        for proveedor_id, nombre, compras, total_saldo, mas_antigua in filas
    ]
