"""Caja (#28, RF-17, RF-18, RN-02, RN-03, RN-13).

Todo dinero que entra o sale pasa por `registrar_movimiento`: ventas, propinas, domicilios,
abonos, gastos, pagos de compra y movimientos manuales. Siempre va a la caja abierta de la sede:
una caja cerrada no admite movimientos, y una anulación posterior al cierre se registra en la
caja abierta del día en que se anula (RN-03).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar
from app.modules.auth.models import Usuario
from app.modules.caja.models import CajaMovimiento, CajaSesion
from app.modules.caja.schemas import (
    EsperadoMetodo,
    EstadoCaja,
    MovimientoManual,
    MovimientoSalida,
    SesionSalida,
)
from app.modules.configuracion.models import MetodoPago
from app.shared.bd import guardar_unico
from app.shared.errores import Conflicto, ErrorNegocio, NoEncontrado
from app.shared.fechas import ahora

YA_ABIERTA = (
    "CAJA_YA_ABIERTA",
    "Ya hay una caja abierta en esta sede: ciérrala antes de abrir otra.",
)


def caja_abierta(db: Session, sede_id: uuid.UUID, bloquear: bool = False) -> CajaSesion | None:
    consulta = select(CajaSesion).where(
        CajaSesion.sede_id == sede_id, CajaSesion.estado == "abierta"
    )
    if bloquear:
        # Compartido: varias ventas a la vez, pero el cierre (FOR UPDATE) espera a que terminen.
        consulta = consulta.with_for_update(read=True)
    return db.scalar(consulta)


def requerir_caja(db: Session, ctx: Contexto, para: str = "registrar dinero") -> CajaSesion:
    """RN-02: sin caja abierta no se vende ni se recibe dinero."""
    sesion = caja_abierta(db, ctx.sede_id, bloquear=True)
    if sesion is None:
        raise Conflicto("CAJA_CERRADA", f"No hay caja abierta: ábrela para {para}.")
    return sesion


def _metodo(db: Session, ctx: Contexto, metodo_id: uuid.UUID) -> MetodoPago:
    m = db.get(MetodoPago, metodo_id)
    if m is None or m.sede_id != ctx.sede_id:
        raise NoEncontrado("el método de pago", metodo_id)
    return m


def abrir(db: Session, ctx: Contexto, base_inicial: int) -> CajaSesion:
    if caja_abierta(db, ctx.sede_id) is not None:
        raise Conflicto(*YA_ABIERTA)
    sesion = CajaSesion(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        abierta_por=ctx.usuario_id,
        abierta_en=ahora(),
        base_inicial=base_inicial,
        estado="abierta",
    )
    db.add(sesion)
    # Dos aperturas simultáneas: la segunda choca con el índice único parcial.
    guardar_unico(db, *YA_ABIERTA)
    auditar(db, ctx, "abrir", "caja_sesiones", sesion.id, despues={"base_inicial": base_inicial})
    return sesion


def registrar_movimiento(
    db: Session,
    ctx: Contexto,
    *,
    tipo: str,
    metodo_pago_id: uuid.UUID,
    monto: int,
    referencia_tipo: str | None = None,
    referencia_id: uuid.UUID | None = None,
    motivo: str | None = None,
) -> CajaMovimiento:
    """Registra dinero en la caja abierta. `monto` lleva el signo: positivo entra, negativo sale.
    No confirma la transacción: si la operación que lo llama falla, el movimiento se revierte."""
    if monto == 0:
        raise ErrorNegocio("VALIDACION", "El movimiento de caja no puede ser de $0.", status=422)
    sesion = requerir_caja(db, ctx)
    _metodo(db, ctx, metodo_pago_id)
    mov = CajaMovimiento(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        caja_sesion_id=sesion.id,
        tipo=tipo,
        metodo_pago_id=metodo_pago_id,
        monto=monto,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        motivo=motivo,
        usuario_id=ctx.usuario_id,
        fecha=ahora(),
    )
    db.add(mov)
    db.flush()
    return mov


def reversar(
    db: Session, ctx: Contexto, referencia_tipo: str, referencia_id: uuid.UUID, motivo: str
) -> list[CajaMovimiento]:
    """Devuelve el dinero de una operación anulada: un reverso por método con el neto de sus
    movimientos, en la caja abierta hoy (RN-03), aunque la original ya esté cerrada."""
    netos = db.execute(
        select(CajaMovimiento.metodo_pago_id, func.sum(CajaMovimiento.monto))
        .where(
            CajaMovimiento.sede_id == ctx.sede_id,
            CajaMovimiento.referencia_tipo == referencia_tipo,
            CajaMovimiento.referencia_id == referencia_id,
        )
        .group_by(CajaMovimiento.metodo_pago_id)
        .order_by(CajaMovimiento.metodo_pago_id)
    ).all()
    return [
        registrar_movimiento(
            db,
            ctx,
            tipo="reverso_anulacion",
            metodo_pago_id=metodo_id,
            monto=-int(neto),
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            motivo=motivo,
        )
        for metodo_id, neto in netos
        if neto
    ]


def movimiento_manual(db: Session, ctx: Contexto, datos: MovimientoManual) -> CajaMovimiento:
    """RF-18: entradas y salidas que no son ventas (cambio para la caja, retiro de los dueños)."""
    monto = datos.monto if datos.tipo == "entrada_manual" else -datos.monto
    mov = registrar_movimiento(
        db,
        ctx,
        tipo=datos.tipo,
        metodo_pago_id=datos.metodo_pago_id,
        monto=monto,
        motivo=datos.motivo,
    )
    auditar(
        db,
        ctx,
        "crear",
        "caja_movimientos",
        mov.id,
        despues={"tipo": datos.tipo, "monto": monto, "motivo": datos.motivo},
    )
    return mov


def esperado_por_metodo(db: Session, sesion: CajaSesion) -> list[EsperadoMetodo]:
    """RN-13: base inicial (solo en el efectivo principal) + Σ movimientos de la sesión."""
    sumas = dict(
        db.execute(
            select(CajaMovimiento.metodo_pago_id, func.sum(CajaMovimiento.monto))
            .where(CajaMovimiento.caja_sesion_id == sesion.id)
            .group_by(CajaMovimiento.metodo_pago_id)
        ).all()
    )
    metodos = db.scalars(
        select(MetodoPago)
        .where(MetodoPago.sede_id == sesion.sede_id)
        .where(MetodoPago.activo | MetodoPago.id.in_(list(sumas)))
        .order_by(MetodoPago.orden, MetodoPago.nombre)
    ).all()
    principal = next((m.id for m in metodos if m.es_efectivo and m.activo), None)
    return [
        EsperadoMetodo(
            metodo_pago_id=m.id,
            metodo=m.nombre,
            es_efectivo=m.es_efectivo,
            esperado=int(sumas.get(m.id, 0)) + (sesion.base_inicial if m.id == principal else 0),
        )
        for m in metodos
    ]


def sesion_salida(db: Session, sesion: CajaSesion) -> SesionSalida:
    return SesionSalida(
        id=sesion.id,
        estado=sesion.estado,
        abierta_en=sesion.abierta_en,
        abierta_por=sesion.abierta_por,
        responsable=db.scalar(select(Usuario.nombre).where(Usuario.id == sesion.abierta_por)),
        base_inicial=sesion.base_inicial,
        cerrada_en=sesion.cerrada_en,
        cerrada_por=sesion.cerrada_por,
        observacion=sesion.observacion,
    )


def estado(db: Session, ctx: Contexto) -> EstadoCaja:
    sesion = caja_abierta(db, ctx.sede_id)
    if sesion is None:
        return EstadoCaja(abierta=False)
    return EstadoCaja(
        abierta=True, sesion=sesion_salida(db, sesion), esperado=esperado_por_metodo(db, sesion)
    )


def movimiento_salida(db: Session, mov: CajaMovimiento) -> MovimientoSalida:
    salida = MovimientoSalida.model_validate(mov, from_attributes=True)
    salida.metodo = db.scalar(select(MetodoPago.nombre).where(MetodoPago.id == mov.metodo_pago_id))
    salida.usuario = db.scalar(select(Usuario.nombre).where(Usuario.id == mov.usuario_id))
    return salida


def movimientos_de(db: Session, ctx: Contexto, sesion_id: uuid.UUID) -> list[MovimientoSalida]:
    sesion = db.get(CajaSesion, sesion_id)
    if sesion is None or sesion.sede_id != ctx.sede_id:
        raise NoEncontrado("la caja", sesion_id)
    movs = db.scalars(
        select(CajaMovimiento)
        .where(CajaMovimiento.caja_sesion_id == sesion_id)
        .order_by(CajaMovimiento.fecha.desc())
    ).all()
    return [movimiento_salida(db, m) for m in movs]
