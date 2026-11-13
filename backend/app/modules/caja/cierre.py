"""Cierre de caja con arqueo (#32, RF-19, RF-20, RN-13, RN-14, RN-18) y su historial.

Flujo del mockup "Cierre de caja": 1) liquidar domicilios (Fase 3, #40), 2) contar el dinero
por método contra lo esperado, 3) confirmar y cerrar. La diferencia se guarda tal cual, sin
ajustes, y exige observación si no es cero.
"""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.modules.auditoria.service import auditar
from app.modules.caja.models import CajaArqueo, CajaMovimiento, CajaSesion
from app.modules.caja.schemas import (
    ArqueoSalida,
    CerrarCaja,
    LineaEfectivo,
    ResumenTurno,
    SesionDetalle,
    SesionResumen,
    VistaCierre,
)
from app.modules.caja.service import caja_abierta, esperado_por_metodo, sesion_salida
from app.modules.configuracion.models import MetodoPago
from app.shared.errores import Conflicto, ErrorNegocio, NoEncontrado
from app.shared.fechas import ahora
from app.shared.paginacion import ParamsPagina, paginar

# "De dónde sale el efectivo": en el orden del mockup; los demás tipos, donde tienen sentido.
CONCEPTOS_EFECTIVO = (
    ("venta", "Ventas en efectivo"),
    ("propina", "Propinas en efectivo"),
    ("abono", "Abonos de encargos"),
    ("saldo_encargo", "Saldos de encargos"),
    ("domicilio", "Domicilios cobrados"),
    ("entrada_manual", "Entradas manuales"),
    ("gasto", "Gastos pagados de la caja"),
    ("pago_compra", "Pagos a proveedores"),
    ("devolucion_abono", "Devoluciones de abonos"),
    ("salida_manual", "Salidas manuales"),
    ("reverso_anulacion", "Anulaciones"),
    ("pago_domiciliario", "Entregado al domiciliario"),
)


def domicilios_sin_liquidar(db: Session, sesion: CajaSesion) -> int:
    """RN-18: no se cierra con domicilios sin liquidar. Los domicilios llegan en la Fase 3 (#40);
    hasta entonces no hay ninguno pendiente."""
    return 0


def _sumas_por_tipo(db: Session, sesion_id: uuid.UUID, solo_efectivo: bool) -> dict[str, int]:
    consulta = (
        select(CajaMovimiento.tipo, func.sum(CajaMovimiento.monto))
        .where(CajaMovimiento.caja_sesion_id == sesion_id)
        .group_by(CajaMovimiento.tipo)
    )
    if solo_efectivo:
        consulta = consulta.join(MetodoPago, MetodoPago.id == CajaMovimiento.metodo_pago_id).where(
            MetodoPago.es_efectivo
        )
    return {tipo: int(total) for tipo, total in db.execute(consulta).all()}


def _efectivo(db: Session, sesion: CajaSesion) -> list[LineaEfectivo]:
    sumas = _sumas_por_tipo(db, sesion.id, solo_efectivo=True)
    lineas = [LineaEfectivo(concepto="Base inicial", monto=sesion.base_inicial)]
    lineas += [
        LineaEfectivo(concepto=texto, monto=sumas[tipo])
        for tipo, texto in CONCEPTOS_EFECTIVO
        if sumas.get(tipo)
    ]
    return lineas


def _resumen(db: Session, sesion: CajaSesion) -> ResumenTurno:
    s = _sumas_por_tipo(db, sesion.id, solo_efectivo=False)
    return ResumenTurno(
        ventas=s.get("venta", 0),
        abonos=s.get("abono", 0) + s.get("saldo_encargo", 0),
        propinas=s.get("propina", 0),
        gastos=-s.get("gasto", 0),
        domicilios_entregados=-s.get("pago_domiciliario", 0),
        pagos_proveedores=-s.get("pago_compra", 0),
        anulaciones=-s.get("reverso_anulacion", 0),
    )


def vista_previa(db: Session, ctx: Contexto) -> VistaCierre:
    sesion = caja_abierta(db, ctx.sede_id)
    if sesion is None:
        raise Conflicto("CAJA_CERRADA", "No hay caja abierta para cerrar.")
    esperado = esperado_por_metodo(db, sesion)
    return VistaCierre(
        sesion=sesion_salida(db, sesion),
        arqueo=[ArqueoSalida(**e.model_dump()) for e in esperado],
        efectivo=_efectivo(db, sesion),
        efectivo_esperado=sum(e.esperado for e in esperado if e.es_efectivo),
        resumen=_resumen(db, sesion),
        domicilios_sin_liquidar=domicilios_sin_liquidar(db, sesion),
    )


def cerrar(db: Session, ctx: Contexto, datos: CerrarCaja) -> CajaSesion:
    sesion = db.scalar(
        select(CajaSesion)
        .where(CajaSesion.sede_id == ctx.sede_id, CajaSesion.estado == "abierta")
        # Exclusivo: espera a que terminen las ventas en curso y bloquea las nuevas.
        .with_for_update()
    )
    if sesion is None:
        raise Conflicto("CAJA_CERRADA", "No hay caja abierta para cerrar.")
    if pendientes := domicilios_sin_liquidar(db, sesion):
        raise Conflicto(
            "DOMICILIOS_SIN_LIQUIDAR",
            f"Hay {pendientes} domicilios sin liquidar: entrégale al domiciliario lo suyo antes "
            "de cerrar.",
        )
    esperado = {e.metodo_pago_id: e for e in esperado_por_metodo(db, sesion)}
    contado = {c.metodo_pago_id: c.contado for c in datos.contado}
    desconocidos = set(contado) - set(esperado)
    if desconocidos:
        raise NoEncontrado("el método de pago", next(iter(desconocidos)))
    sin_contar = [e.metodo for m, e in esperado.items() if e.esperado and m not in contado]
    if sin_contar:
        raise ErrorNegocio(
            "FALTA_CONTAR",
            f"Falta escribir lo contado en: {', '.join(sin_contar)}.",
            {"metodos": sin_contar},
            status=422,
        )
    diferencias = {m: contado.get(m, 0) - e.esperado for m, e in esperado.items()}
    observacion = (datos.observacion or "").strip() or None
    if any(diferencias.values()) and observacion is None:
        raise ErrorNegocio(
            "OBSERVACION_REQUERIDA",
            "Hay diferencias entre lo contado y lo esperado: escribe una observación.",
            {"diferencias": {esperado[m].metodo: d for m, d in diferencias.items() if d}},
            status=422,
        )
    for m, e in esperado.items():
        db.add(
            CajaArqueo(
                sede_id=ctx.sede_id,
                caja_sesion_id=sesion.id,
                metodo_pago_id=m,
                esperado=e.esperado,
                contado=contado.get(m, 0),
                diferencia=diferencias[m],
            )
        )
    sesion.estado = "cerrada"
    sesion.cerrada_por = ctx.usuario_id
    sesion.cerrada_en = ahora()
    sesion.observacion = observacion
    db.flush()
    auditar(
        db,
        ctx,
        "cerrar",
        "caja_sesiones",
        sesion.id,
        despues={
            "diferencias": {esperado[m].metodo: d for m, d in diferencias.items()},
            "observacion": observacion,
        },
    )
    return sesion


# --- Historial (RF-20) ----------------------------------------------------------------------


def _arqueos(db: Session, sesion: CajaSesion) -> list[ArqueoSalida]:
    if sesion.estado == "abierta":
        return [ArqueoSalida(**e.model_dump()) for e in esperado_por_metodo(db, sesion)]
    filas = db.execute(
        select(CajaArqueo, MetodoPago.nombre, MetodoPago.es_efectivo)
        .join(MetodoPago, MetodoPago.id == CajaArqueo.metodo_pago_id)
        .where(CajaArqueo.caja_sesion_id == sesion.id)
        .order_by(MetodoPago.orden, MetodoPago.nombre)
    ).all()
    return [
        ArqueoSalida(
            metodo_pago_id=a.metodo_pago_id,
            metodo=nombre,
            es_efectivo=efectivo,
            esperado=a.esperado,
            contado=a.contado,
            diferencia=a.diferencia,
        )
        for a, nombre, efectivo in filas
    ]


def _resumen_sesion(db: Session, sesion: CajaSesion) -> SesionResumen:
    arqueos = _arqueos(db, sesion)
    cerrada = sesion.estado == "cerrada"
    return SesionResumen(
        **sesion_salida(db, sesion).model_dump(),
        efectivo_esperado=sum(a.esperado for a in arqueos if a.es_efectivo),
        diferencia_total=sum(a.diferencia or 0 for a in arqueos) if cerrada else None,
    )


def _visible(ctx: Contexto):
    """Quien no ve reportes generales solo ve las cajas que abrió o cerró."""
    if "reportes.ver" in ctx.permisos:
        return True
    return or_(CajaSesion.abierta_por == ctx.usuario_id, CajaSesion.cerrada_por == ctx.usuario_id)


def listar(db: Session, ctx: Contexto, params: ParamsPagina) -> tuple[list[SesionResumen], int]:
    consulta = (
        select(CajaSesion)
        .where(CajaSesion.sede_id == ctx.sede_id, _visible(ctx))
        .order_by(CajaSesion.abierta_en.desc())
    )
    filas, total = paginar(db, consulta, params)
    return [_resumen_sesion(db, s) for s in filas], total


def detalle(db: Session, ctx: Contexto, sesion_id: uuid.UUID) -> SesionDetalle:
    sesion = db.scalar(
        select(CajaSesion).where(
            CajaSesion.id == sesion_id, CajaSesion.sede_id == ctx.sede_id, _visible(ctx)
        )
    )
    if sesion is None:
        raise NoEncontrado("la caja", sesion_id)
    return SesionDetalle(
        **_resumen_sesion(db, sesion).model_dump(),
        arqueos=_arqueos(db, sesion),
        efectivo=_efectivo(db, sesion),
        resumen=_resumen(db, sesion),
    )
