"""Domicilios y liquidación al domiciliario (#40, RF-13, RF-19, RN-18).

El valor del domicilio se cobra con la venta y entra a la caja como movimiento `domicilio`, que
no suma en ventas ni en utilidad. Antes de cerrar, la caja le entrega a cada domiciliario lo
suyo (`pago_domiciliario`, negativo) y marca sus domicilios con `liquidado_en`.
"""

import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar
from app.modules.caja import service as caja
from app.modules.caja.models import CajaSesion
from app.modules.clientes.models import Cliente
from app.modules.clientes.service import normalizar_telefono
from app.modules.domicilios.models import Domiciliario, Domicilio
from app.modules.domicilios.schemas import (
    DomiciliarioCrear,
    DomiciliarioEditar,
    DomicilioCambio,
    DomicilioEntrada,
    DomicilioSalida,
    LiquidacionDomiciliario,
    LiquidacionTurno,
    LiquidarEntrada,
)
from app.modules.encargos.models import Encargo
from app.modules.ventas.models import Venta
from app.shared.bd import guardar_unico
from app.shared.errores import Conflicto, ErrorNegocio, NoEncontrado
from app.shared.fechas import ahora, zona

DUPLICADO = ("NOMBRE_DUPLICADO", "Ya hay un domiciliario con ese nombre.")

# --- Domiciliarios --------------------------------------------------------------------------


def listar_domiciliarios(db: Session, ctx: Contexto, incluir_inactivos: bool) -> list[Domiciliario]:
    consulta = (
        select(Domiciliario)
        .where(Domiciliario.sede_id == ctx.sede_id)
        .order_by(Domiciliario.nombre)
    )
    if not incluir_inactivos:
        consulta = consulta.where(Domiciliario.activo)
    return list(db.scalars(consulta))


def obtener_domiciliario(db: Session, ctx: Contexto, domiciliario_id: uuid.UUID) -> Domiciliario:
    d = db.get(Domiciliario, domiciliario_id)
    if d is None or d.sede_id != ctx.sede_id:
        raise NoEncontrado("el domiciliario", domiciliario_id)
    return d


def crear_domiciliario(db: Session, ctx: Contexto, datos: DomiciliarioCrear) -> Domiciliario:
    d = Domiciliario(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        nombre=" ".join(datos.nombre.split()),
        telefono=normalizar_telefono(datos.telefono),
        activo=True,
    )
    db.add(d)
    guardar_unico(db, *DUPLICADO)
    auditar(db, ctx, "crear", "domiciliarios", d.id, despues={"nombre": d.nombre})
    return d


def editar_domiciliario(
    db: Session, ctx: Contexto, domiciliario_id: uuid.UUID, datos: DomiciliarioEditar
) -> Domiciliario:
    d = obtener_domiciliario(db, ctx, domiciliario_id)
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("nombre"):
        d.nombre = " ".join(cambios["nombre"].split())
    if "telefono" in cambios:
        d.telefono = normalizar_telefono(cambios["telefono"])
    if cambios.get("activo") is not None:
        d.activo = cambios["activo"]
    guardar_unico(db, *DUPLICADO)
    auditar(db, ctx, "editar", "domiciliarios", d.id, despues={"nombre": d.nombre})
    return d


# --- Domicilios -----------------------------------------------------------------------------


def crear_para_venta(
    db: Session,
    ctx: Contexto,
    venta: Venta,
    datos: DomicilioEntrada,
    encargo_id: uuid.UUID | None = None,
) -> Domicilio:
    domiciliario = obtener_domiciliario(db, ctx, datos.domiciliario_id)
    if not domiciliario.activo:
        raise ErrorNegocio(
            "DOMICILIARIO_INACTIVO", f"{domiciliario.nombre} está inactivo.", status=422
        )
    d = Domicilio(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        venta_id=venta.id,
        encargo_id=encargo_id,
        cliente_id=venta.cliente_id,
        contacto=(datos.contacto or "").strip() or None,
        direccion=datos.direccion.strip(),
        telefono=normalizar_telefono(datos.telefono),
        domiciliario_id=domiciliario.id,
        valor=venta.valor_domicilio,
        estado="pendiente",
        caja_sesion_id=venta.caja_sesion_id,
    )
    db.add(d)
    db.flush()
    return d


def cancelar_de_venta(db: Session, venta_id: uuid.UUID) -> None:
    """Al anular la venta, su domicilio sin liquidar se cancela: el dinero ya volvió al cliente
    con el reverso, así que no hay nada que entregarle al domiciliario."""
    for d in db.scalars(
        select(Domicilio).where(Domicilio.venta_id == venta_id, Domicilio.liquidado_en.is_(None))
    ):
        d.estado = "cancelado"
    db.flush()


def _salidas(db: Session, domicilios: list[Domicilio]) -> list[DomicilioSalida]:
    if not domicilios:
        return []
    ventas = {
        v.id: v
        for v in db.scalars(select(Venta).where(Venta.id.in_({d.venta_id for d in domicilios})))
    }
    encargos = dict(
        db.execute(
            select(Encargo.id, Encargo.numero).where(
                Encargo.id.in_({d.encargo_id for d in domicilios if d.encargo_id})
            )
        ).all()
    )
    clientes = dict(
        db.execute(
            select(Cliente.id, Cliente.nombre).where(
                Cliente.id.in_({d.cliente_id for d in domicilios if d.cliente_id})
            )
        ).all()
    )
    domiciliarios = dict(
        db.execute(
            select(Domiciliario.id, Domiciliario.nombre).where(
                Domiciliario.id.in_({d.domiciliario_id for d in domicilios})
            )
        ).all()
    )
    return [
        DomicilioSalida(
            id=d.id,
            fecha=d.creado_en,
            venta_id=d.venta_id,
            venta_numero=ventas[d.venta_id].numero,
            encargo_id=d.encargo_id,
            encargo_numero=encargos.get(d.encargo_id),
            cliente_id=d.cliente_id,
            cliente=clientes.get(d.cliente_id) or d.contacto,
            direccion=d.direccion,
            telefono=d.telefono,
            domiciliario_id=d.domiciliario_id,
            domiciliario=domiciliarios.get(d.domiciliario_id, ""),
            valor=d.valor,
            total_venta=ventas[d.venta_id].total,
            estado=d.estado,
            liquidado_en=d.liquidado_en,
        )
        for d in domicilios
    ]


def listar(
    db: Session,
    ctx: Contexto,
    desde: date,
    hasta: date,
    estado: str | None,
    domiciliario_id: uuid.UUID | None,
) -> list[DomicilioSalida]:
    inicio = datetime.combine(desde, time(), tzinfo=zona())
    fin = datetime.combine(hasta + timedelta(days=1), time(), tzinfo=zona())
    consulta = (
        select(Domicilio)
        .where(Domicilio.sede_id == ctx.sede_id, Domicilio.creado_en >= inicio)
        .where(Domicilio.creado_en < fin)
        .order_by(Domicilio.creado_en.desc())
    )
    if estado:
        consulta = consulta.where(Domicilio.estado == estado)
    if domiciliario_id:
        consulta = consulta.where(Domicilio.domiciliario_id == domiciliario_id)
    return _salidas(db, list(db.scalars(consulta)))


def cambiar(
    db: Session, ctx: Contexto, domicilio_id: uuid.UUID, datos: DomicilioCambio
) -> DomicilioSalida:
    d = db.scalar(
        select(Domicilio)
        .where(Domicilio.id == domicilio_id, Domicilio.sede_id == ctx.sede_id)
        .with_for_update()
    )
    if d is None:
        raise NoEncontrado("el domicilio", domicilio_id)
    if d.estado == "cancelado":
        raise Conflicto("DOMICILIO_CANCELADO", "Ese domicilio se canceló con su venta.")
    antes = {"estado": d.estado, "domiciliario_id": str(d.domiciliario_id)}
    if datos.domiciliario_id and datos.domiciliario_id != d.domiciliario_id:
        if d.liquidado_en is not None:
            raise Conflicto(
                "DOMICILIO_LIQUIDADO",
                "Ya se le entregó el dinero a ese domiciliario: no se puede cambiar.",
            )
        d.domiciliario_id = obtener_domiciliario(db, ctx, datos.domiciliario_id).id
    if datos.estado:
        d.estado = datos.estado
    db.flush()
    auditar(
        db,
        ctx,
        "editar",
        "domicilios",
        d.id,
        antes=antes,
        despues={"estado": d.estado, "domiciliario_id": str(d.domiciliario_id)},
    )
    return _salidas(db, [d])[0]


# --- Liquidación (paso 1 del cierre) --------------------------------------------------------


def sin_liquidar(db: Session, sesion: CajaSesion) -> int:
    """RN-18: domicilios cobrados en esta caja que aún no se le entregan al domiciliario."""
    return (
        db.scalar(
            select(func.count()).where(
                Domicilio.caja_sesion_id == sesion.id,
                Domicilio.estado != "cancelado",
                Domicilio.liquidado_en.is_(None),
                Domicilio.valor > 0,
            )
        )
        or 0
    )


def liquidacion(db: Session, sesion: CajaSesion) -> LiquidacionTurno:
    pendiente = func.coalesce(func.sum(Domicilio.valor).filter(Domicilio.liquidado_en.is_(None)), 0)
    filas = db.execute(
        select(
            Domiciliario.id,
            Domiciliario.nombre,
            func.count(),
            func.coalesce(func.sum(Domicilio.valor), 0),
            pendiente,
        )
        .join(Domiciliario, Domiciliario.id == Domicilio.domiciliario_id)
        .where(Domicilio.caja_sesion_id == sesion.id, Domicilio.estado != "cancelado")
        .group_by(Domiciliario.id, Domiciliario.nombre)
        .order_by(Domiciliario.nombre)
    ).all()
    lineas = [
        LiquidacionDomiciliario(
            domiciliario_id=i,
            domiciliario=nombre,
            domicilios=n,
            cobrado=int(cobrado),
            entregado=int(cobrado) - int(debe),
            pendiente=int(debe),
        )
        for i, nombre, n, cobrado, debe in filas
    ]
    return LiquidacionTurno(
        domicilios=sum(x.domicilios for x in lineas),
        cobrado=sum(x.cobrado for x in lineas),
        entregado=sum(x.entregado for x in lineas),
        pendiente=sum(x.pendiente for x in lineas),
        domiciliarios=lineas,
    )


def liquidar(db: Session, ctx: Contexto, datos: LiquidarEntrada) -> LiquidacionTurno:
    """Le entrega al domiciliario lo cobrado por sus domicilios de la caja abierta."""
    sesion = caja.requerir_caja(db, ctx, "liquidar domicilios")
    domiciliario = obtener_domiciliario(db, ctx, datos.domiciliario_id)
    pendientes = db.scalars(
        select(Domicilio)
        .where(
            Domicilio.caja_sesion_id == sesion.id,
            Domicilio.domiciliario_id == domiciliario.id,
            Domicilio.estado != "cancelado",
            Domicilio.liquidado_en.is_(None),
        )
        .with_for_update()
    ).all()
    total = sum(d.valor for d in pendientes)
    if total == 0:
        raise Conflicto(
            "NADA_QUE_LIQUIDAR",
            f"No hay domicilios pendientes de entregar a {domiciliario.nombre}.",
        )
    if datos.monto is not None and datos.monto != total:
        raise Conflicto(
            "LIQUIDACION_CAMBIO",
            f"A {domiciliario.nombre} ahora se le deben ${total:,}".replace(",", ".")
            + ": revisa antes de entregar.",
            {"pendiente": total},
        )
    mov = caja.registrar_movimiento(
        db,
        ctx,
        tipo="pago_domiciliario",
        metodo_pago_id=datos.metodo_pago_id or caja.efectivo_principal(db, ctx.sede_id),
        monto=-total,
        referencia_tipo="domiciliario",
        referencia_id=domiciliario.id,
        motivo=f"{len(pendientes)} domicilios de {domiciliario.nombre}",
    )
    momento = ahora()
    for d in pendientes:
        d.liquidado_en = momento
    db.flush()
    auditar(
        db,
        ctx,
        "liquidar",
        "domiciliarios",
        domiciliario.id,
        despues={"monto": total, "domicilios": len(pendientes), "movimiento": str(mov.id)},
    )
    return liquidacion(db, sesion)
