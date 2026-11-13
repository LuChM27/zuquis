"""Registro de ventas (#29, RF-08 a RF-13, RF-16, RN-02, RN-04, RN-06, RN-08, RN-15).

Una venta se guarda en una sola transacción: cabecera, ítems con el precio del momento,
consumo de inventario por PEPS con su costo real, pagos y movimientos de caja. Si cualquier
parte falla (falta inventario, la caja está cerrada, los pagos no cuadran) no queda nada.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar
from app.modules.auth.models import Usuario
from app.modules.caja import service as caja
from app.modules.carta.models import Modificador, Producto
from app.modules.carta.service import receta_vigente
from app.modules.configuracion import service as configuracion
from app.modules.configuracion.models import MetodoPago
from app.modules.inventario import motor
from app.modules.inventario.models import Insumo
from app.modules.produccion.service import cantidades_por_insumo
from app.modules.ventas.models import (
    Consecutivo,
    Venta,
    VentaItem,
    VentaItemModificador,
    VentaPago,
)
from app.modules.ventas.schemas import (
    DescuentoEntrada,
    ItemSalida,
    ModificadorSalida,
    PagoSalida,
    VentaCrear,
    VentaSalida,
)
from app.shared.dinero import aplicar_porcentaje, costo_linea
from app.shared.errores import ErrorNegocio, NoEncontrado
from app.shared.fechas import ahora, zona
from app.shared.paginacion import ParamsPagina, RangoFechas, paginar


def siguiente_numero(db: Session, sede_id: uuid.UUID, tipo: str) -> int:
    """RN-04: consecutivo por sede sin repetir. La fila se bloquea hasta el final de la
    transacción; si la venta falla, el número no se consume."""
    db.execute(
        insert(Consecutivo)
        .values(sede_id=sede_id, tipo=tipo, ultimo=0)
        .on_conflict_do_nothing(index_elements=["sede_id", "tipo"])
    )
    fila = db.scalar(
        select(Consecutivo)
        .where(Consecutivo.sede_id == sede_id, Consecutivo.tipo == tipo)
        .with_for_update()
    )
    fila.ultimo += 1
    return fila.ultimo


def monto_descuento(base: int, descuento: DescuentoEntrada | None) -> int:
    """Pesos que descuenta sobre `base`, redondeado a peso (ROUND_HALF_UP)."""
    if descuento is None:
        return 0
    monto = (
        aplicar_porcentaje(base, descuento.valor)
        if descuento.tipo == "porcentaje"
        else int(descuento.valor)
    )
    if monto > base:
        raise ErrorNegocio(
            "DESCUENTO_INVALIDO",
            "El descuento es mayor que el valor al que se aplica.",
            {"base": base, "descuento": monto},
            status=422,
        )
    return monto


@dataclass
class _Linea:
    """Un ítem del carrito ya validado y con precios calculados."""

    entrada: object
    producto: Producto
    modificadores: list[Modificador]
    precios_mods: list[int]
    bruto: int
    descuento: int
    item: VentaItem | None = None
    costo: int = 0
    costos_mods: list[int] = field(default_factory=list)


def _productos(db: Session, ctx: Contexto, datos: VentaCrear) -> dict[uuid.UUID, Producto]:
    ids = {i.producto_id for i in datos.items}
    productos = {
        p.id: p
        for p in db.scalars(
            select(Producto)
            .where(Producto.id.in_(ids), Producto.sede_id == ctx.sede_id)
            .options(selectinload(Producto.modificadores))
        )
    }
    for pid in ids:
        p = productos.get(pid)
        if p is None or not p.activo:
            raise NoEncontrado("el producto", pid)
        if not p.disponible:
            raise ErrorNegocio(
                "PRODUCTO_AGOTADO",
                f"{p.nombre} está marcado como agotado.",
                {"producto_id": str(p.id)},
                status=409,
            )
    return productos


def _lineas(db: Session, ctx: Contexto, datos: VentaCrear) -> list[_Linea]:
    productos = _productos(db, ctx, datos)
    lineas = []
    for entrada in datos.items:
        producto = productos[entrada.producto_id]
        permitidos = {m.id: m for m in producto.modificadores if m.activo}
        mods = []
        for mid in entrada.modificador_ids:
            if mid not in permitidos:
                raise ErrorNegocio(
                    "ADICION_NO_APLICA",
                    f"Esa adición no se ofrece en {producto.nombre}.",
                    {"producto_id": str(producto.id), "modificador_id": str(mid)},
                    status=422,
                )
            mods.append(permitidos[mid])
        # Las adiciones son por unidad: su precio se multiplica por la cantidad del ítem.
        precios_mods = [costo_linea(entrada.cantidad, Decimal(m.precio)) for m in mods]
        bruto = costo_linea(entrada.cantidad, Decimal(producto.precio)) + sum(precios_mods)
        lineas.append(
            _Linea(
                entrada=entrada,
                producto=producto,
                modificadores=mods,
                precios_mods=precios_mods,
                bruto=bruto,
                descuento=monto_descuento(bruto, entrada.descuento),
            )
        )
    return lineas


def _validar_pagos(db: Session, ctx: Contexto, datos: VentaCrear, cobrado: int) -> dict:
    metodos = {
        m.id: m
        for m in db.scalars(
            select(MetodoPago).where(
                MetodoPago.id.in_([p.metodo_pago_id for p in datos.pagos]),
                MetodoPago.sede_id == ctx.sede_id,
                MetodoPago.activo,
            )
        )
    }
    for p in datos.pagos:
        metodo = metodos.get(p.metodo_pago_id)
        if metodo is None:
            raise NoEncontrado("el método de pago", p.metodo_pago_id)
        if p.recibido is not None and not metodo.es_efectivo:
            raise ErrorNegocio(
                "VALIDACION", "Solo en efectivo se indica con cuánto paga.", status=422
            )
        if p.recibido is not None and p.recibido < p.monto:
            raise ErrorNegocio(
                "VALIDACION",
                "Lo recibido en efectivo no alcanza para ese pago.",
                {"monto": p.monto, "recibido": p.recibido},
                status=422,
            )
    suma = sum(p.monto for p in datos.pagos)
    if suma != cobrado:
        raise ErrorNegocio(
            "PAGOS_NO_CUADRAN",
            "Los pagos no suman lo que se cobra (venta + propina + domicilio).",
            {"cobrado": cobrado, "pagos": suma, "diferencia": cobrado - suma},
            status=422,
        )
    return metodos


@dataclass(order=True)
class _Necesidad:
    """Lo que hay que sacar de inventario para una línea (o una adición de la línea)."""

    tipo_item: str
    item_id: uuid.UUID
    linea: int
    adicion: int  # -1: el producto; n: la adición n de la línea
    cantidad: Decimal = field(compare=False)


def _necesidades(db: Session, lineas: list[_Linea]) -> list[_Necesidad]:
    necesidades = []
    for n, linea in enumerate(lineas):
        cantidad = linea.entrada.cantidad
        p = linea.producto
        if p.tipo == "lote":
            # RN-08: unidades del lote terminado más antiguo.
            necesidades.append(_Necesidad("producto", p.id, n, -1, cantidad))
        else:
            # RN-06: los insumos de la receta vigente × cantidad vendida.
            receta = receta_vigente(db, producto_id=p.id)
            if receta is None:
                raise ErrorNegocio(
                    "SIN_RECETA",
                    f"{p.nombre} no tiene receta, así que no se sabe qué descontar del "
                    "inventario. Créala en la Carta antes de venderlo.",
                    {"producto_id": str(p.id)},
                    status=422,
                )
            for insumo_id, c in cantidades_por_insumo(receta, cantidad):
                necesidades.append(_Necesidad("insumo", insumo_id, n, -1, c))
        for a, m in enumerate(linea.modificadores):
            receta = receta_vigente(db, modificador_id=m.id)
            if receta is not None:  # una adición sin receta no descuenta inventario
                for insumo_id, c in cantidades_por_insumo(receta, cantidad):
                    necesidades.append(_Necesidad("insumo", insumo_id, n, a, c))
    # Siempre en el mismo orden de ítem: dos ventas simultáneas bloquean lotes sin cruzarse.
    return sorted(necesidades)


def _consumir(
    db: Session, ctx: Contexto, venta: Venta, lineas: list[_Linea], permitir_faltante: bool
) -> None:
    for linea in lineas:
        linea.costos_mods = [0] * len(linea.modificadores)
    for nec in _necesidades(db, lineas):
        linea = lineas[nec.linea]
        try:
            resultado = motor.consumir(
                db,
                ctx,
                tipo_item=nec.tipo_item,
                item_id=nec.item_id,
                cantidad=nec.cantidad,
                tipo_mov="venta",
                referencia_tipo="venta",
                referencia_id=venta.id,
                permitir_faltante=permitir_faltante,
            )
        except motor.StockInsuficiente as exc:
            nombre = (
                linea.producto.nombre
                if nec.tipo_item == "producto"
                else db.get(Insumo, nec.item_id).nombre
            )
            exc.detalle["nombre"] = nombre
            exc.detalle["producto"] = linea.producto.nombre
            exc.mensaje = (
                f"No hay suficiente {nombre} en vitrina."
                if nec.tipo_item == "producto"
                else f"No alcanza {nombre} para preparar {linea.producto.nombre}."
            )
            raise
        costo = resultado.costo_total
        if resultado.faltante:
            # RF-16: lo vendido sin stock se costea al último costo de compra (estimado).
            estimado = motor.ultimo_costo(db, ctx.sede_id, nec.tipo_item, nec.item_id) or 0
            costo += costo_linea(resultado.faltante, Decimal(estimado))
        if nec.adicion < 0:
            linea.costo += costo
        else:
            linea.costos_mods[nec.adicion] += costo


def _movimientos_caja(db: Session, ctx: Contexto, venta: Venta, datos: VentaCrear) -> None:
    """Reparte los pagos, en el orden en que llegan, entre venta, propina (RN-15) y domicilio
    (RN-18): cada concepto queda en su propio movimiento de caja por método."""
    pendientes = [
        ["venta", venta.total],
        ["propina", venta.propina],
        ["domicilio", venta.valor_domicilio],
    ]
    totales: dict[tuple[str, uuid.UUID], int] = {}
    for pago in datos.pagos:
        resto = pago.monto
        for concepto in pendientes:
            tomar = min(resto, concepto[1])
            if tomar:
                clave = (concepto[0], pago.metodo_pago_id)
                totales[clave] = totales.get(clave, 0) + tomar
                concepto[1] -= tomar
                resto -= tomar
    for (tipo, metodo_id), monto in totales.items():
        caja.registrar_movimiento(
            db,
            ctx,
            tipo=tipo,
            metodo_pago_id=metodo_id,
            monto=monto,
            referencia_tipo="venta",
            referencia_id=venta.id,
        )


def crear(db: Session, ctx: Contexto, datos: VentaCrear) -> Venta:
    sesion = caja.requerir_caja(db, ctx, "vender")
    lineas = _lineas(db, ctx, datos)

    subtotal = sum(linea.bruto for linea in lineas)
    descuento_items = sum(linea.descuento for linea in lineas)
    descuento_venta = monto_descuento(subtotal - descuento_items, datos.descuento)
    descuento_total = descuento_items + descuento_venta
    total = subtotal - descuento_total
    cobrado = total + datos.propina + datos.valor_domicilio
    _validar_pagos(db, ctx, datos, cobrado)

    motivos = [d.motivo for d in [datos.descuento, *(i.descuento for i in datos.items)] if d]
    venta = Venta(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        numero=siguiente_numero(db, ctx.sede_id, "venta"),
        caja_sesion_id=sesion.id,
        tipo_servicio=datos.tipo_servicio,
        cliente_id=datos.cliente_id,
        subtotal=subtotal,
        descuento_total=descuento_total,
        valor_domicilio=datos.valor_domicilio,
        total=total,
        propina=datos.propina,
        estado="pagada",
        descuento_motivo="; ".join(dict.fromkeys(motivos)) or None,
        usuario_id=ctx.usuario_id,
        fecha=ahora(),
    )
    db.add(venta)
    db.flush()

    _consumir(
        db, ctx, venta, lineas, configuracion.valor(db, ctx.sede_id, "permitir_venta_sin_stock")
    )

    for orden, linea in enumerate(lineas):
        item = VentaItem(
            id=uuid.uuid4(),
            sede_id=ctx.sede_id,
            venta_id=venta.id,
            producto_id=linea.producto.id,
            cantidad=linea.entrada.cantidad,
            precio_unitario=linea.producto.precio,
            bruto=linea.bruto,
            descuento=linea.descuento,
            subtotal=linea.bruto - linea.descuento,
            costo_total=linea.costo,
            nota=linea.entrada.nota,
            orden=orden,
        )
        item.modificadores = [
            VentaItemModificador(
                sede_id=ctx.sede_id,
                modificador_id=m.id,
                precio=precio,
                costo_total=costo,
                orden=a,
            )
            for a, (m, precio, costo) in enumerate(
                zip(linea.modificadores, linea.precios_mods, linea.costos_mods, strict=True)
            )
        ]
        venta.items.append(item)
    venta.pagos = [
        VentaPago(
            sede_id=ctx.sede_id,
            metodo_pago_id=p.metodo_pago_id,
            monto=p.monto,
            recibido=p.recibido,
            orden=orden,
        )
        for orden, p in enumerate(datos.pagos)
    ]
    venta.costo_total = sum(linea.costo + sum(linea.costos_mods) for linea in lineas)
    db.flush()

    _movimientos_caja(db, ctx, venta, datos)
    auditar(
        db,
        ctx,
        "crear",
        "ventas",
        venta.id,
        despues={
            "numero": venta.numero,
            "total": total,
            "propina": venta.propina,
            "descuento_total": descuento_total,
        },
    )
    return venta


# --- Consultas ------------------------------------------------------------------------------


def obtener(db: Session, ctx: Contexto, venta_id: uuid.UUID, bloquear: bool = False) -> Venta:
    consulta = select(Venta).where(Venta.id == venta_id, Venta.sede_id == ctx.sede_id)
    if bloquear:
        consulta = consulta.with_for_update()
    venta = db.scalar(consulta)
    if venta is None:
        raise NoEncontrado("la venta", venta_id)
    return venta


def salida(db: Session, v: Venta) -> VentaSalida:
    productos = dict(
        db.execute(
            select(Producto.id, Producto.nombre).where(
                Producto.id.in_({i.producto_id for i in v.items})
            )
        ).all()
    )
    mod_ids = {m.modificador_id for i in v.items for m in i.modificadores}
    mods = dict(
        db.execute(
            select(Modificador.id, Modificador.nombre).where(Modificador.id.in_(mod_ids))
        ).all()
    )
    metodos = dict(
        db.execute(
            select(MetodoPago.id, MetodoPago.nombre).where(
                MetodoPago.id.in_({p.metodo_pago_id for p in v.pagos})
            )
        ).all()
    )
    pagos = [
        PagoSalida(
            metodo_pago_id=p.metodo_pago_id,
            metodo=metodos.get(p.metodo_pago_id, ""),
            monto=p.monto,
            recibido=p.recibido,
            cambio=(p.recibido - p.monto) if p.recibido is not None else 0,
        )
        for p in v.pagos
    ]
    return VentaSalida(
        id=v.id,
        numero=v.numero,
        fecha=v.fecha,
        caja_sesion_id=v.caja_sesion_id,
        tipo_servicio=v.tipo_servicio,
        cliente_id=v.cliente_id,
        items=[
            ItemSalida(
                id=i.id,
                producto_id=i.producto_id,
                producto=productos.get(i.producto_id, ""),
                cantidad=i.cantidad,
                precio_unitario=i.precio_unitario,
                modificadores=[
                    ModificadorSalida(
                        modificador_id=m.modificador_id,
                        nombre=mods.get(m.modificador_id, ""),
                        precio=m.precio,
                        costo_total=m.costo_total,
                    )
                    for m in i.modificadores
                ],
                bruto=i.bruto,
                descuento=i.descuento,
                subtotal=i.subtotal,
                costo_total=i.costo_total,
                nota=i.nota,
            )
            for i in v.items
        ],
        subtotal=v.subtotal,
        descuento_total=v.descuento_total,
        descuento_motivo=v.descuento_motivo,
        total=v.total,
        propina=v.propina,
        valor_domicilio=v.valor_domicilio,
        cobrado=v.total + v.propina + v.valor_domicilio,
        cambio=sum(p.cambio for p in pagos),
        costo_total=v.costo_total,
        pagos=pagos,
        estado=v.estado,
        cajero=db.scalar(select(Usuario.nombre).where(Usuario.id == v.usuario_id)),
        motivo_anulacion=v.motivo_anulacion,
        anulada_en=v.anulada_en,
    )


def listar(
    db: Session,
    ctx: Contexto,
    params: ParamsPagina,
    rango: RangoFechas,
    caja_sesion_id: uuid.UUID | None,
    estado: str | None,
) -> tuple[list[VentaSalida], int]:
    consulta = select(Venta).where(Venta.sede_id == ctx.sede_id).order_by(Venta.numero.desc())
    if caja_sesion_id:
        consulta = consulta.where(Venta.caja_sesion_id == caja_sesion_id)
    if estado:
        consulta = consulta.where(Venta.estado == estado)
    if rango.desde:
        consulta = consulta.where(
            Venta.fecha >= datetime.combine(rango.desde, time(), tzinfo=zona())
        )
    if rango.hasta:
        fin = datetime.combine(rango.hasta + timedelta(days=1), time(), tzinfo=zona())
        consulta = consulta.where(Venta.fecha < fin)
    filas, total = paginar(db, consulta, params)
    return [salida(db, v) for v in filas], total
