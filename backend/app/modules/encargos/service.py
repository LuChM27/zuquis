"""Encargos y abonos (#41, #42, RF-34 a RF-39, RN-19 a RN-23).

El dinero de un encargo pasa por la caja en tres momentos: cada abono el día que se recibe
(`abono`), el saldo al entregar (`saldo_encargo`) y, si se cancela, la devolución
(`devolucion_abono`). La venta nace al entregar: ese día cuenta en ventas y utilidad (RN-20).
"""

import uuid
from collections import Counter
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar
from app.modules.caja import service as caja
from app.modules.carta.models import Producto
from app.modules.clientes import service as clientes
from app.modules.clientes.models import Cliente
from app.modules.configuracion.models import MetodoPago
from app.modules.encargos.models import ACTIVOS, Encargo, EncargoAbono, EncargoItem
from app.modules.encargos.schemas import (
    AbonoEntrada,
    AbonoSalida,
    CancelacionEntrada,
    ClienteBreve,
    ConteoDia,
    EncargoCrear,
    EncargoEditar,
    EncargoSalida,
    EntregaEntrada,
    GastoBreve,
    GastoDecoracionEntrada,
    ItemEntrada,
    ItemSalida,
)
from app.modules.gastos import service as gastos
from app.modules.gastos.models import Gasto
from app.modules.gastos.schemas import GastoCrear
from app.modules.ventas import service as ventas
from app.modules.ventas.models import Venta
from app.shared.dinero import costo_linea
from app.shared.errores import Conflicto, ErrorNegocio, NoEncontrado
from app.shared.fechas import ahora, zona
from app.shared.paginacion import ParamsPagina, paginar

EN_PRODUCCION = (
    "ENCARGO_EN_PRODUCCION",
    "El encargo ya pasó a producción; solo un administrador puede cancelarlo",
)
# pendiente → en producción → listo. Entregar y cancelar tienen su propia operación.
SIGUIENTE = {"pendiente": "en_produccion", "en_produccion": "listo"}
NOMBRES = {
    "pendiente": "pendiente",
    "en_produccion": "en producción",
    "listo": "listo",
    "entregado": "entregado",
    "cancelado": "cancelado",
}


def obtener(db: Session, ctx: Contexto, encargo_id: uuid.UUID, bloquear: bool = False) -> Encargo:
    consulta = select(Encargo).where(Encargo.id == encargo_id, Encargo.sede_id == ctx.sede_id)
    if bloquear:
        consulta = consulta.with_for_update()
    encargo = db.scalar(consulta)
    if encargo is None:
        raise NoEncontrado("el encargo", encargo_id)
    return encargo


def abonado(encargo: Encargo) -> int:
    return sum(a.monto for a in encargo.abonos if a.estado == "vigente")


def _requerir_activo(encargo: Encargo, para: str) -> None:
    if encargo.estado not in ACTIVOS:
        raise Conflicto(
            "ENCARGO_CERRADO",
            f"El encargo ya está {NOMBRES[encargo.estado]}: no se puede {para}.",
            {"estado": encargo.estado},
        )


def _en_zona(momento: datetime) -> datetime:
    """Una fecha sin zona se entiende en la hora del negocio."""
    return momento if momento.tzinfo else momento.replace(tzinfo=zona())


def _items(db: Session, ctx: Contexto, entradas: list[ItemEntrada]) -> list[EncargoItem]:
    ids = {i.producto_id for i in entradas if i.producto_id}
    productos = {
        p.id: p
        for p in db.scalars(
            select(Producto).where(Producto.id.in_(ids), Producto.sede_id == ctx.sede_id)
        )
    }
    items = []
    for orden, e in enumerate(entradas):
        producto = productos.get(e.producto_id) if e.producto_id else None
        if e.producto_id and (producto is None or not producto.activo):
            raise NoEncontrado("el producto", e.producto_id)
        items.append(
            EncargoItem(
                id=uuid.uuid4(),
                sede_id=ctx.sede_id,
                producto_id=producto.id if producto else None,
                descripcion=(e.descripcion or "").strip() or producto.nombre,
                cantidad=e.cantidad,
                precio=e.precio if e.precio is not None else producto.precio,
                orden=orden,
                decoracion=e.decoracion,
                decoracion_precio=e.decoracion_precio,
            )
        )
    return items


def _total(items: list[EncargoItem]) -> int:
    total = sum(
        costo_linea(i.cantidad, Decimal(i.precio)) + (i.decoracion_precio or 0) for i in items
    )
    if total <= 0:
        raise ErrorNegocio("VALIDACION", "El encargo debe valer más de $0.", status=422)
    return total


def _descripcion(items: list[EncargoItem]) -> str:
    def cantidad(c: Decimal) -> str:
        return format(c.normalize(), "f").replace(".", ",")

    partes = [
        i.descripcion if i.cantidad == 1 else f"{cantidad(i.cantidad)} × {i.descripcion}"
        for i in items
    ]
    return ", ".join(partes)[:200]


def _direccion(tipo_entrega: str, direccion: str | None, cliente: Cliente) -> str | None:
    if tipo_entrega != "domicilio":
        return None
    direccion = (direccion or "").strip() or cliente.direccion
    if not direccion:
        raise ErrorNegocio(
            "VALIDACION", "Un encargo a domicilio necesita la dirección de entrega.", status=422
        )
    return direccion


def crear(db: Session, ctx: Contexto, datos: EncargoCrear) -> Encargo:
    cliente = clientes.obtener(db, ctx, datos.cliente_id)
    items = _items(db, ctx, datos.items)
    encargo = Encargo(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        numero=ventas.siguiente_numero(db, ctx.sede_id, "encargo"),
        cliente_id=cliente.id,
        descripcion=(datos.descripcion or "").strip() or _descripcion(items),
        fecha_entrega=_en_zona(datos.fecha_entrega),
        tipo_entrega=datos.tipo_entrega,
        direccion_entrega=_direccion(datos.tipo_entrega, datos.direccion_entrega, cliente),
        observaciones=(datos.observaciones or "").strip() or None,
        total=_total(items),
        estado="pendiente",
        usuario_id=ctx.usuario_id,
        items=items,
    )
    db.add(encargo)
    db.flush()
    auditar(
        db,
        ctx,
        "crear",
        "encargos",
        encargo.id,
        despues={"numero": encargo.numero, "total": encargo.total},
    )
    if datos.abono is not None:
        _abonar(db, ctx, encargo, datos.abono)
    return encargo


def editar(db: Session, ctx: Contexto, encargo_id: uuid.UUID, datos: EncargoEditar) -> Encargo:
    encargo = obtener(db, ctx, encargo_id, bloquear=True)
    if encargo.estado in ("en_produccion", "listo"):
        raise Conflicto(*EN_PRODUCCION)  # RN-23
    _requerir_activo(encargo, "editar")
    cambios = datos.model_dump(exclude_unset=True)
    antes = {"total": encargo.total, "fecha_entrega": encargo.fecha_entrega.isoformat()}
    if cambios.get("cliente_id"):
        encargo.cliente_id = clientes.obtener(db, ctx, datos.cliente_id).id
    if cambios.get("fecha_entrega"):
        encargo.fecha_entrega = _en_zona(datos.fecha_entrega)
    if "observaciones" in cambios:
        encargo.observaciones = (datos.observaciones or "").strip() or None
    if datos.items is not None:
        automatica = encargo.descripcion == _descripcion(encargo.items)
        items = _items(db, ctx, datos.items)
        total = _total(items)
        if total < abonado(encargo):
            raise ErrorNegocio(
                "ABONO_EXCEDE_SALDO",
                "El total no puede quedar por debajo de lo que ya se abonó.",
                {"total": total, "abonado": abonado(encargo)},
                status=422,
            )
        encargo.items = items
        encargo.total = total
        if automatica and "descripcion" not in cambios:
            encargo.descripcion = _descripcion(items)
    if "descripcion" in cambios:
        encargo.descripcion = (datos.descripcion or "").strip() or _descripcion(encargo.items)
    if cambios.get("tipo_entrega") or "direccion_entrega" in cambios:
        encargo.tipo_entrega = datos.tipo_entrega or encargo.tipo_entrega
        direccion = (
            datos.direccion_entrega if "direccion_entrega" in cambios else encargo.direccion_entrega
        )
        cliente = db.get(Cliente, encargo.cliente_id)
        encargo.direccion_entrega = _direccion(encargo.tipo_entrega, direccion, cliente)
    db.flush()
    auditar(
        db,
        ctx,
        "editar",
        "encargos",
        encargo.id,
        antes=antes,
        despues={"total": encargo.total, "fecha_entrega": encargo.fecha_entrega.isoformat()},
    )
    return encargo


def cambiar_estado(db: Session, ctx: Contexto, encargo_id: uuid.UUID, estado: str) -> Encargo:
    encargo = obtener(db, ctx, encargo_id, bloquear=True)
    if SIGUIENTE.get(encargo.estado) != estado:
        if estado == "entregado":
            mensaje = "Para entregarlo usa «Entregar y cobrar»: ahí se cobra el saldo."
        elif estado == "cancelado":
            mensaje = "Para cancelarlo usa «Cancelar encargo»: ahí se decide qué pasa con el abono."
        else:
            mensaje = f"Un encargo {NOMBRES[encargo.estado]} no puede pasar a {NOMBRES[estado]}."
        raise Conflicto("TRANSICION_INVALIDA", mensaje, {"de": encargo.estado, "a": estado})
    antes = encargo.estado
    encargo.estado = estado
    db.flush()
    auditar(
        db,
        ctx,
        "estado",
        "encargos",
        encargo.id,
        antes={"estado": antes},
        despues={"estado": estado},
    )
    return encargo


# --- Abonos (RN-19, RN-20) ------------------------------------------------------------------


def _abonar(db: Session, ctx: Contexto, encargo: Encargo, datos: AbonoEntrada) -> EncargoAbono:
    sesion = caja.requerir_caja(db, ctx, "recibir el abono")
    saldo = encargo.total - abonado(encargo)
    if datos.monto > saldo:
        raise ErrorNegocio(
            "ABONO_EXCEDE_SALDO",
            "El abono es mayor que el saldo del encargo.",
            {"saldo": saldo, "abono": datos.monto},
            status=422,
        )
    abono = EncargoAbono(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        encargo_id=encargo.id,
        monto=datos.monto,
        metodo_pago_id=datos.metodo_pago_id,
        caja_sesion_id=sesion.id,
        estado="vigente",
        usuario_id=ctx.usuario_id,
        fecha=ahora(),
    )
    encargo.abonos.append(abono)
    db.flush()
    caja.registrar_movimiento(
        db,
        ctx,
        tipo="abono",
        metodo_pago_id=datos.metodo_pago_id,
        monto=datos.monto,
        referencia_tipo="encargo_abono",
        referencia_id=abono.id,
        motivo=f"Abono al encargo {encargo.numero}",
    )
    auditar(
        db,
        ctx,
        "abonar",
        "encargos",
        encargo.id,
        despues={"numero": encargo.numero, "monto": datos.monto},
    )
    return abono


def abonar(db: Session, ctx: Contexto, encargo_id: uuid.UUID, datos: AbonoEntrada) -> Encargo:
    encargo = obtener(db, ctx, encargo_id, bloquear=True)
    _requerir_activo(encargo, "recibir abonos")
    _abonar(db, ctx, encargo, datos)
    return encargo


def anular_abono(
    db: Session, ctx: Contexto, encargo_id: uuid.UUID, abono_id: uuid.UUID, motivo: str
) -> Encargo:
    encargo = obtener(db, ctx, encargo_id, bloquear=True)
    _requerir_activo(encargo, "anular abonos")
    abono = next((a for a in encargo.abonos if a.id == abono_id), None)
    if abono is None:
        raise NoEncontrado("el abono", abono_id)
    if abono.estado == "anulado":
        raise Conflicto("YA_ANULADO", "Ese abono ya se anuló.")
    caja.requerir_caja(db, ctx, "anular el abono (el dinero se devuelve desde la caja)")
    caja.reversar(
        db,
        ctx,
        "encargo_abono",
        abono.id,
        f"Anulación de abono del encargo {encargo.numero}: {motivo}",
    )
    abono.estado = "anulado"
    abono.motivo_anulacion = motivo
    abono.anulado_por = ctx.usuario_id
    abono.anulado_en = ahora()
    db.flush()
    auditar(
        db,
        ctx,
        "anular_abono",
        "encargos",
        encargo.id,
        despues={"numero": encargo.numero, "monto": abono.monto, "motivo": motivo},
    )
    return encargo


# --- Entrega y cancelación (RN-21, RN-22) ---------------------------------------------------


def entregar(db: Session, ctx: Contexto, encargo_id: uuid.UUID, datos: EntregaEntrada) -> Encargo:
    encargo = obtener(db, ctx, encargo_id, bloquear=True)
    _requerir_activo(encargo, "entregar")
    if encargo.estado != "listo":
        raise Conflicto(
            "TRANSICION_INVALIDA",
            f"El encargo está {NOMBRES[encargo.estado]}: márcalo como listo antes de entregarlo.",
            {"de": encargo.estado, "a": "entregado"},
        )
    a_domicilio = encargo.tipo_entrega == "domicilio"
    if a_domicilio != (datos.domicilio is not None) or (datos.valor_domicilio and not a_domicilio):
        raise ErrorNegocio(
            "VALIDACION",
            "Indica el domiciliario que lo lleva."
            if a_domicilio
            else "Este encargo lo recogen en el local: no lleva domicilio.",
            status=422,
        )
    venta = ventas.crear_de_encargo(
        db,
        ctx,
        encargo,
        abonado=abonado(encargo),
        pagos=datos.pagos,
        valor_domicilio=datos.valor_domicilio,
        domicilio=datos.domicilio,
    )
    encargo.estado = "entregado"
    encargo.venta_id = venta.id
    encargo.entregado_en = ahora()
    db.flush()
    auditar(
        db,
        ctx,
        "entregar",
        "encargos",
        encargo.id,
        despues={"numero": encargo.numero, "venta": venta.numero, "total": encargo.total},
    )
    return encargo


def cancelar(
    db: Session, ctx: Contexto, encargo_id: uuid.UUID, datos: CancelacionEntrada
) -> Encargo:
    encargo = obtener(db, ctx, encargo_id, bloquear=True)
    _requerir_activo(encargo, "cancelar")
    recibido = abonado(encargo)
    if datos.decision == "devuelve_total" or recibido == 0:
        decision, devuelto = "devuelve_total", recibido
    elif datos.decision == "retiene":
        decision, devuelto = "retiene", 0
    else:
        decision, devuelto = "devuelve_parcial", datos.monto_devuelto
        if not 0 < devuelto < recibido:
            raise ErrorNegocio(
                "DEVOLUCION_INVALIDA",
                "Una devolución parcial debe ser mayor que $0 y menor que lo abonado.",
                {"abonado": recibido, "monto_devuelto": devuelto},
                status=422,
            )
    if devuelto:
        caja.requerir_caja(db, ctx, "devolver el abono")
        caja.registrar_movimiento(
            db,
            ctx,
            tipo="devolucion_abono",
            metodo_pago_id=datos.metodo_pago_id or caja.efectivo_principal(db, ctx.sede_id),
            monto=-devuelto,
            referencia_tipo="encargo",
            referencia_id=encargo.id,
            motivo=f"Devolución de abono del encargo {encargo.numero}",
        )
    antes = encargo.estado
    encargo.estado = "cancelado"
    encargo.decision_cancelacion = decision
    encargo.monto_devuelto = devuelto
    encargo.monto_retenido = recibido - devuelto
    encargo.motivo_cancelacion = (datos.motivo or "").strip() or None
    encargo.cancelado_por = ctx.usuario_id
    encargo.cancelado_en = ahora()
    db.flush()
    auditar(
        db,
        ctx,
        "cancelar",
        "encargos",
        encargo.id,
        antes={"estado": antes},
        despues={
            "numero": encargo.numero,
            "decision": decision,
            "devuelto": devuelto,
            "retenido": recibido - devuelto,
            "motivo": encargo.motivo_cancelacion,
        },
    )
    return encargo


def registrar_gasto(
    db: Session, ctx: Contexto, encargo_id: uuid.UUID, datos: GastoDecoracionEntrada
) -> Encargo:
    """Materiales de decoración: se registra como gasto de la categoría de decoración, ligado
    al encargo. Vale en cualquier estado: los materiales se compran antes de entregar y, si el
    encargo se cancela, la plata ya salió."""
    encargo = obtener(db, ctx, encargo_id)
    gasto = gastos.crear(
        db,
        ctx,
        GastoCrear(
            categoria_id=gastos.categoria_decoracion(db, ctx).id,
            descripcion=datos.descripcion,
            monto=datos.monto,
            metodo_pago_id=datos.metodo_pago_id,
            fuente=datos.fuente,
        ),
        encargo_id=encargo.id,
    )
    auditar(
        db,
        ctx,
        "gasto_decoracion",
        "encargos",
        encargo.id,
        despues={"numero": encargo.numero, "gasto": str(gasto.id), "monto": gasto.monto},
    )
    return encargo


# --- Consultas ------------------------------------------------------------------------------


def salida(db: Session, e: Encargo) -> EncargoSalida:
    cliente = db.get(Cliente, e.cliente_id)
    metodos = dict(
        db.execute(
            select(MetodoPago.id, MetodoPago.nombre).where(
                MetodoPago.id.in_({a.metodo_pago_id for a in e.abonos})
            )
        ).all()
    )
    recibido = abonado(e)
    gastos_deco = list(
        db.scalars(
            select(Gasto).where(Gasto.encargo_id == e.id).order_by(Gasto.fecha, Gasto.creado_en)
        )
    )
    return EncargoSalida(
        id=e.id,
        numero=e.numero,
        cliente=ClienteBreve(
            id=cliente.id,
            nombre=cliente.nombre,
            telefono=cliente.telefono,
            direccion=cliente.direccion,
        ),
        descripcion=e.descripcion,
        fecha_entrega=e.fecha_entrega,
        tipo_entrega=e.tipo_entrega,
        direccion_entrega=e.direccion_entrega,
        observaciones=e.observaciones,
        items=[
            ItemSalida(
                id=i.id,
                producto_id=i.producto_id,
                descripcion=i.descripcion,
                cantidad=i.cantidad,
                precio=i.precio,
                subtotal=costo_linea(i.cantidad, Decimal(i.precio)),
                decoracion=i.decoracion,
                decoracion_precio=i.decoracion_precio,
            )
            for i in e.items
        ],
        total=e.total,
        abonado=recibido,
        saldo=e.total - recibido if e.estado in ACTIVOS else 0,
        estado=e.estado,
        editable=e.estado == "pendiente",
        abonos=[
            AbonoSalida(
                id=a.id,
                monto=a.monto,
                metodo_pago_id=a.metodo_pago_id,
                metodo=metodos.get(a.metodo_pago_id, ""),
                fecha=a.fecha,
                estado=a.estado,
                motivo_anulacion=a.motivo_anulacion,
            )
            for a in e.abonos
        ],
        creado_en=e.creado_en,
        venta_id=e.venta_id,
        venta_numero=db.scalar(select(Venta.numero).where(Venta.id == e.venta_id))
        if e.venta_id
        else None,
        entregado_en=e.entregado_en,
        decision_cancelacion=e.decision_cancelacion,
        monto_devuelto=e.monto_devuelto,
        monto_retenido=e.monto_retenido,
        motivo_cancelacion=e.motivo_cancelacion,
        cancelado_en=e.cancelado_en,
        decoracion_cobrada=sum(i.decoracion_precio or 0 for i in e.items),
        gasto_decoracion=sum(g.monto for g in gastos_deco if g.estado == "registrado"),
        gastos_decoracion=[
            GastoBreve(
                id=g.id,
                fecha=g.fecha,
                descripcion=g.descripcion,
                monto=g.monto,
                fuente=g.fuente,
                estado=g.estado,
            )
            for g in gastos_deco
        ],
    )


def _rango(desde: date | None, hasta: date | None) -> list:
    filtros = []
    if desde:
        filtros.append(Encargo.fecha_entrega >= datetime.combine(desde, time(), tzinfo=zona()))
    if hasta:
        fin = datetime.combine(hasta + timedelta(days=1), time(), tzinfo=zona())
        filtros.append(Encargo.fecha_entrega < fin)
    return filtros


def listar(
    db: Session,
    ctx: Contexto,
    params: ParamsPagina,
    desde: date | None,
    hasta: date | None,
    estado: str | None,
    cliente_id: uuid.UUID | None,
    q: str | None,
) -> tuple[list[EncargoSalida], int]:
    """Por fecha de entrega (RF-39), de la más cercana a la más lejana."""
    consulta = (
        select(Encargo)
        .where(Encargo.sede_id == ctx.sede_id, *_rango(desde, hasta))
        .options(selectinload(Encargo.items), selectinload(Encargo.abonos))
        .order_by(Encargo.fecha_entrega, Encargo.numero)
    )
    if estado:
        consulta = consulta.where(Encargo.estado == estado)
    if cliente_id:
        consulta = consulta.where(Encargo.cliente_id == cliente_id)
    if q and q.strip():
        texto = q.strip()
        filtros = [Encargo.descripcion.ilike(f"%{texto}%"), Cliente.nombre.ilike(f"%{texto}%")]
        if texto.lstrip("0").isdigit():
            filtros.append(Encargo.numero == int(texto))
        consulta = consulta.join(Cliente, Cliente.id == Encargo.cliente_id).where(or_(*filtros))
    filas, total = paginar(db, consulta, params)
    return [salida(db, e) for e in filas], total


def conteo(db: Session, ctx: Contexto, desde: date, hasta: date) -> list[ConteoDia]:
    """Encargos por día de entrega (sin los cancelados), con los días vacíos en cero."""
    fechas = db.scalars(
        select(Encargo.fecha_entrega).where(
            Encargo.sede_id == ctx.sede_id, Encargo.estado != "cancelado", *_rango(desde, hasta)
        )
    ).all()
    por_dia = Counter(f.astimezone(zona()).date() for f in fechas)
    dias = (hasta - desde).days + 1
    return [
        ConteoDia(
            fecha=desde + timedelta(days=n), encargos=por_dia.get(desde + timedelta(days=n), 0)
        )
        for n in range(dias)
    ]
