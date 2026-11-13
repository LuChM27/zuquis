"""Motor de inventario: lotes, libro de movimientos y consumo PEPS (#18).

Toda entrada y salida de existencias pasa por aquí: compras, producción, ventas (Fase 2),
mermas, ajustes y anulaciones. Las funciones no confirman la transacción: el servicio que las
llama decide, y si algo falla después, todo se revierte (§8: una transacción por operación).

Reglas: RN-05 (PEPS por fecha de ingreso), RN-09 (Σ lotes = Σ movimientos), RN-10 (ajuste
positivo al costo del último lote), RN-11 (vencidos bloqueados salvo merma), RN-12 (el reverso
vuelve a los mismos lotes con su costo original).
"""

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.modules.inventario.models import FaltanteInventario, Lote, MovimientoInventario
from app.shared.dinero import ESCALA_CANTIDAD, a_decimal, costo_linea
from app.shared.errores import Conflicto, ErrorNegocio
from app.shared.fechas import ahora, hoy

CERO = Decimal(0)


class StockInsuficiente(ErrorNegocio):
    status = 409

    def __init__(self, tipo_item: str, item_id: uuid.UUID, requerido: Decimal, disponible: Decimal):
        super().__init__(
            "STOCK_INSUFICIENTE",
            "No hay suficiente inventario para esta operación.",
            {
                "tipo_item": tipo_item,
                "item_id": str(item_id),
                "requerido": str(requerido.quantize(ESCALA_CANTIDAD)),
                "disponible": str(disponible.quantize(ESCALA_CANTIDAD)),
            },
        )


@dataclass
class Consumo:
    lote_id: uuid.UUID
    cantidad: Decimal  # positiva
    costo_unitario: Decimal
    costo_total: int  # positivo, redondeado a peso por línea


@dataclass
class ResultadoConsumo:
    consumos: list[Consumo] = field(default_factory=list)
    faltante: Decimal = CERO

    @property
    def costo_total(self) -> int:
        """Suma de líneas ya redondeadas (§6)."""
        return sum(c.costo_total for c in self.consumos)


def _cantidad(valor: Decimal) -> Decimal:
    dec = a_decimal(valor)
    if dec != dec.quantize(ESCALA_CANTIDAD):
        raise ErrorNegocio("VALIDACION", "Las cantidades admiten máximo 4 decimales.", status=422)
    return dec.quantize(ESCALA_CANTIDAD)


def _movimiento(
    db: Session,
    ctx: Contexto,
    lote: Lote,
    tipo: str,
    cantidad: Decimal,
    costo_total: int,
    referencia_tipo: str,
    referencia_id: uuid.UUID,
    costo_unitario: Decimal | None = None,
) -> MovimientoInventario:
    mov = MovimientoInventario(
        sede_id=lote.sede_id,
        tipo=tipo,
        tipo_item=lote.tipo_item,
        item_id=lote.item_id,
        lote_id=lote.id,
        cantidad=cantidad,
        costo_unitario=lote.costo_unitario if costo_unitario is None else costo_unitario,
        costo_total=costo_total,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        usuario_id=ctx.usuario_id,
        fecha=ahora(),
    )
    db.add(mov)
    return mov


def _vigente(consulta, incluir_vencidos: bool):
    if incluir_vencidos:
        return consulta
    return consulta.where(or_(Lote.fecha_vencimiento.is_(None), Lote.fecha_vencimiento >= hoy()))


# --- Consultas ------------------------------------------------------------------------------


def stock(
    db: Session,
    sede_id: uuid.UUID,
    tipo_item: str,
    item_id: uuid.UUID,
    incluir_vencidos: bool = True,
) -> Decimal:
    """RN-09: el stock es la suma de cantidad_disponible de los lotes."""
    consulta = select(func.coalesce(func.sum(Lote.cantidad_disponible), 0)).where(
        Lote.sede_id == sede_id, Lote.tipo_item == tipo_item, Lote.item_id == item_id
    )
    return Decimal(db.scalar(_vigente(consulta, incluir_vencidos)))


def ultimo_costo(
    db: Session,
    sede_id: uuid.UUID,
    tipo_item: str,
    item_id: uuid.UUID,
    origen: str | None = None,
) -> Decimal | None:
    """Costo unitario del lote más reciente del ítem (opcionalmente solo de un origen)."""
    consulta = select(Lote.costo_unitario).where(
        Lote.sede_id == sede_id, Lote.tipo_item == tipo_item, Lote.item_id == item_id
    )
    if origen:
        consulta = consulta.where(Lote.origen == origen)
    return db.scalar(consulta.order_by(Lote.fecha_ingreso.desc()).limit(1))


# --- Entradas -------------------------------------------------------------------------------


def crear_lote(
    db: Session,
    ctx: Contexto,
    *,
    tipo_item: str,
    item_id: uuid.UUID,
    origen: str,
    origen_id: uuid.UUID | None,
    cantidad: Decimal,
    costo_unitario: Decimal,
    tipo_mov: str,
    referencia_tipo: str,
    referencia_id: uuid.UUID,
    vence: date | None = None,
) -> Lote:
    """Crea un lote con su movimiento de entrada y regulariza los faltantes abiertos del ítem."""
    cantidad = _cantidad(cantidad)
    if cantidad <= 0:
        raise ErrorNegocio("VALIDACION", "La cantidad debe ser mayor que cero.", status=422)
    costo_unitario = a_decimal(costo_unitario)
    if costo_unitario < 0:
        raise ErrorNegocio("VALIDACION", "El costo no puede ser negativo.", status=422)
    lote = Lote(
        id=uuid.uuid4(),
        sede_id=ctx.sede_id,
        tipo_item=tipo_item,
        item_id=item_id,
        origen=origen,
        origen_id=origen_id,
        cantidad_inicial=cantidad,
        cantidad_disponible=cantidad,
        costo_unitario=costo_unitario,
        # Hora exacta (no la del inicio de la transacción) para que el orden PEPS sea estable
        # aun con varios lotes creados en la misma operación.
        fecha_ingreso=ahora(),
        fecha_vencimiento=vence,
    )
    db.add(lote)
    db.flush()
    _movimiento(
        db,
        ctx,
        lote,
        tipo_mov,
        cantidad,
        costo_linea(cantidad, costo_unitario),
        referencia_tipo,
        referencia_id,
    )
    _regularizar_faltantes(db, ctx, lote)
    db.flush()
    return lote


def _regularizar_faltantes(db: Session, ctx: Contexto, lote: Lote) -> None:
    """Lo vendido sin stock se descuenta del lote nuevo, con su costo real (decisión #2).
    El movimiento queda con la referencia de la venta original, así su anulación lo devuelve."""
    faltantes = db.scalars(
        select(FaltanteInventario)
        .where(
            FaltanteInventario.sede_id == lote.sede_id,
            FaltanteInventario.tipo_item == lote.tipo_item,
            FaltanteInventario.item_id == lote.item_id,
            FaltanteInventario.estado == "abierto",
        )
        .order_by(FaltanteInventario.creado_en, FaltanteInventario.id)
        .with_for_update()
    ).all()
    for faltante in faltantes:
        if lote.cantidad_disponible <= 0:
            break
        tomar = min(faltante.cantidad_pendiente, lote.cantidad_disponible)
        lote.cantidad_disponible -= tomar
        mov = _movimiento(
            db,
            ctx,
            lote,
            "venta",
            -tomar,
            -costo_linea(tomar, lote.costo_unitario),
            faltante.referencia_tipo,
            faltante.referencia_id,
        )
        db.flush()
        faltante.cantidad_pendiente -= tomar
        if faltante.cantidad_pendiente == 0:
            faltante.estado = "regularizado"
            faltante.regularizado_por_mov_id = mov.id


def ajuste_positivo(
    db: Session,
    ctx: Contexto,
    *,
    tipo_item: str,
    item_id: uuid.UUID,
    cantidad: Decimal,
    referencia_id: uuid.UUID,
    costo_unitario: Decimal | None = None,
    vence: date | None = None,
) -> Lote:
    """RN-10: lote de origen ajuste al costo del último lote del ítem. Sin lotes previos, el
    costo se tiene que indicar (no se inventa un costo)."""
    if costo_unitario is None:
        costo_unitario = ultimo_costo(db, ctx.sede_id, tipo_item, item_id)
    if costo_unitario is None:
        raise ErrorNegocio(
            "COSTO_REQUERIDO",
            "Este ítem no tiene lotes anteriores: indica el costo unitario del ajuste.",
            {"tipo_item": tipo_item, "item_id": str(item_id)},
            status=422,
        )
    return crear_lote(
        db,
        ctx,
        tipo_item=tipo_item,
        item_id=item_id,
        origen="ajuste",
        origen_id=referencia_id,
        cantidad=cantidad,
        costo_unitario=costo_unitario,
        tipo_mov="ajuste",
        referencia_tipo="ajuste",
        referencia_id=referencia_id,
        vence=vence,
    )


# --- Salidas --------------------------------------------------------------------------------


def consumir(
    db: Session,
    ctx: Contexto,
    *,
    tipo_item: str,
    item_id: uuid.UUID,
    cantidad: Decimal,
    tipo_mov: str,
    referencia_tipo: str,
    referencia_id: uuid.UUID,
    incluir_vencidos: bool = False,
    lote_id: uuid.UUID | None = None,
    permitir_faltante: bool = False,
) -> ResultadoConsumo:
    """Consume por PEPS: lote con fecha de ingreso más antigua primero, una fila de movimiento
    por lote (RN-05). Los lotes se bloquean (FOR UPDATE) para que dos operaciones simultáneas
    no dejen cantidades negativas. Los vencidos solo se consumen si se indica (mermas, RN-11).

    Con ``permitir_faltante`` (venta sin stock, RF-16) lo que no alcanza queda como faltante
    abierto con costo estimado; si no, se lanza STOCK_INSUFICIENTE y no se mueve nada.
    """
    cantidad = _cantidad(cantidad)
    if cantidad <= 0:
        raise ErrorNegocio("VALIDACION", "La cantidad debe ser mayor que cero.", status=422)

    consulta = select(Lote).where(
        Lote.sede_id == ctx.sede_id,
        Lote.tipo_item == tipo_item,
        Lote.item_id == item_id,
        Lote.cantidad_disponible > 0,
    )
    if lote_id is not None:
        consulta = consulta.where(Lote.id == lote_id)
    consulta = _vigente(consulta, incluir_vencidos or lote_id is not None)
    lotes = db.scalars(consulta.order_by(Lote.fecha_ingreso, Lote.id).with_for_update()).all()

    disponible = sum((lote.cantidad_disponible for lote in lotes), CERO)
    if disponible < cantidad and not permitir_faltante:
        raise StockInsuficiente(tipo_item, item_id, cantidad, disponible)

    resultado = ResultadoConsumo()
    restante = cantidad
    for lote in lotes:
        if restante == 0:
            break
        tomar = min(restante, lote.cantidad_disponible)
        lote.cantidad_disponible -= tomar
        costo = costo_linea(tomar, lote.costo_unitario)
        _movimiento(db, ctx, lote, tipo_mov, -tomar, -costo, referencia_tipo, referencia_id)
        resultado.consumos.append(Consumo(lote.id, tomar, lote.costo_unitario, costo))
        restante -= tomar

    if restante > 0:
        estimado = ultimo_costo(db, ctx.sede_id, tipo_item, item_id) or CERO
        db.add(
            FaltanteInventario(
                sede_id=ctx.sede_id,
                tipo_item=tipo_item,
                item_id=item_id,
                cantidad=restante,
                cantidad_pendiente=restante,
                costo_estimado=costo_linea(restante, estimado),
                referencia_tipo=referencia_tipo,
                referencia_id=referencia_id,
                creado_en=ahora(),
            )
        )
        resultado.faltante = restante
    db.flush()
    return resultado


def reversar(
    db: Session, ctx: Contexto, referencia_tipo: str, referencia_id: uuid.UUID
) -> list[MovimientoInventario]:
    """Anula todos los movimientos de una operación (RN-12): cada salida vuelve a su mismo lote
    con su costo original, y cada entrada se retira de su lote, siempre que nadie la haya
    consumido. Los faltantes abiertos de la operación se anulan."""
    ya = db.scalar(
        select(func.count()).where(
            MovimientoInventario.referencia_tipo == referencia_tipo,
            MovimientoInventario.referencia_id == referencia_id,
            MovimientoInventario.tipo == "reverso_anulacion",
        )
    )
    if ya:
        raise Conflicto("YA_ANULADO", "Esta operación ya se anuló.")

    movimientos = db.scalars(
        select(MovimientoInventario)
        .where(
            MovimientoInventario.referencia_tipo == referencia_tipo,
            MovimientoInventario.referencia_id == referencia_id,
        )
        .order_by(MovimientoInventario.lote_id)
    ).all()
    lotes = {
        lote.id: lote
        for lote in db.scalars(
            select(Lote)
            .where(Lote.id.in_({m.lote_id for m in movimientos}))
            .order_by(Lote.id)
            .with_for_update()
        )
    }
    # Primero se verifica todo y luego se mueve, para no dejar nada a medias.
    for m in movimientos:
        if m.cantidad > 0 and lotes[m.lote_id].cantidad_disponible < m.cantidad:
            raise Conflicto(
                "LOTE_CONSUMIDO",
                "Lo que entró con esta operación ya se usó o se vendió; no se puede anular. "
                "Registra un ajuste si hace falta corregir el inventario.",
                {"lote_id": str(m.lote_id)},
            )

    reversos = []
    for m in movimientos:
        lote = lotes[m.lote_id]
        lote.cantidad_disponible -= m.cantidad  # salida (negativa) suma; entrada resta
        reversos.append(
            _movimiento(
                db,
                ctx,
                lote,
                "reverso_anulacion",
                -m.cantidad,
                -m.costo_total,
                referencia_tipo,
                referencia_id,
                costo_unitario=m.costo_unitario,
            )
        )
    for faltante in db.scalars(
        select(FaltanteInventario).where(
            FaltanteInventario.referencia_tipo == referencia_tipo,
            FaltanteInventario.referencia_id == referencia_id,
            FaltanteInventario.estado == "abierto",
        )
    ):
        faltante.estado = "anulado"
    db.flush()
    return reversos


def verificar(db: Session, sede_id: uuid.UUID) -> tuple[int, list[dict]]:
    """RN-09: por cada lote, Σ movimientos debe ser igual a cantidad_disponible."""
    sumas = (
        select(
            MovimientoInventario.lote_id,
            func.sum(MovimientoInventario.cantidad).label("suma"),
        )
        .where(MovimientoInventario.sede_id == sede_id)
        .group_by(MovimientoInventario.lote_id)
        .subquery()
    )
    # Columnas leídas de la base (no entidades de la sesión) para comparar lo que hay guardado.
    filas = db.execute(
        select(
            Lote.id,
            Lote.tipo_item,
            Lote.item_id,
            Lote.cantidad_disponible,
            func.coalesce(sumas.c.suma, 0),
        )
        .outerjoin(sumas, sumas.c.lote_id == Lote.id)
        .where(Lote.sede_id == sede_id)
    ).all()
    diferencias = [
        {
            "lote_id": str(lote_id),
            "tipo_item": tipo_item,
            "item_id": str(item_id),
            "en_lote": str(disponible),
            "en_movimientos": str(Decimal(suma).quantize(ESCALA_CANTIDAD)),
        }
        for lote_id, tipo_item, item_id, disponible, suma in filas
        if Decimal(suma) != disponible
    ]
    return len(filas), diferencias
