"""Reporte de movimientos con código PUC para el contador (RF-43, docs/puc-propuesta.md).

Es un listado por cuenta (decidido con el usuario), no un libro diario de partida doble: cada
concepto del día va con su cuenta y al final hay un subtotal por cuenta. Se agrupa por día para
que el contador pase totales diarios a su programa. Si una categoría o un método de pago no
tiene código, sale como "Sin código" para que salte a la vista.
"""

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.caja.models import CajaMovimiento
from app.modules.configuracion.models import MetodoPago
from app.modules.encargos.models import Encargo, EncargoAbono
from app.modules.gastos.models import CategoriaGasto, Gasto
from app.modules.inventario.models import Merma
from app.modules.reportes.cifras import _del_periodo, _suma, es_cortesia, local
from app.modules.reportes.esquemas import Reporte, col, seccion
from app.modules.reportes.periodo import Periodo
from app.modules.reportes.tablas import nuevo
from app.modules.ventas.models import Venta

SIN_CODIGO = "Sin código"
VENTAS, DESCUENTOS, COSTO_VENTAS = "4120", "4175", "6120"
DIVERSOS_GASTO, DIVERSOS_INGRESO = "5295", "4295"
TERCEROS, ANTICIPOS = "2380", "2805"
# Dinero que entra a la caja por estos movimientos se registra en la cuenta de su método.
TIPOS_RECIBIDO = ("venta", "propina", "domicilio", "abono", "saldo_encargo")


def _dia(columna):
    return func.to_char(local(columna), "YYYY-MM-DD")


def movimientos(db: Session, p: Periodo) -> list[dict]:
    inicio, fin = p.limites()
    filas: list[dict] = []

    def agregar(dia: str, concepto: str, cuenta: str | None, monto, n: int | None = None):
        if monto:
            filas.append(
                {
                    "fecha": dia,
                    "concepto": concepto,
                    "referencia": f"{n} registros" if n else "",
                    "cuenta": cuenta or SIN_CODIGO,
                    "monto": int(monto),
                }
            )

    dia = _dia(Venta.fecha)
    cortesia = es_cortesia()
    for d, n, bruto, desc, costo, prop, dom, costo_cort in db.execute(
        select(
            dia,
            func.count().filter(~cortesia),
            func.sum(Venta.subtotal).filter(~cortesia),
            func.sum(Venta.descuento_total).filter(~cortesia),
            func.sum(Venta.costo_total).filter(~cortesia),
            _suma(Venta.propina),
            _suma(Venta.valor_domicilio),
            func.sum(Venta.costo_total).filter(cortesia),
        )
        .where(*_del_periodo(p))
        .group_by(dia)
    ).all():
        agregar(d, "Ventas (valor bruto)", VENTAS, bruto, n)
        agregar(d, "Descuentos en ventas", DESCUENTOS, desc)
        agregar(d, "Costo de ventas (PEPS)", COSTO_VENTAS, costo)
        agregar(d, "Cortesías por su costo", DIVERSOS_GASTO, costo_cort)
        agregar(d, "Propinas (de terceros)", TERCEROS, prop)
        agregar(d, "Domicilios (de terceros)", TERCEROS, dom)

    dia = _dia(Merma.fecha)
    for d, monto in db.execute(
        select(dia, func.sum(Merma.costo_total))
        .where(Merma.sede_id == p.sede_id, Merma.fecha >= inicio, Merma.fecha < fin)
        .group_by(dia)
    ).all():
        agregar(d, "Mermas de inventario", DIVERSOS_GASTO, monto)

    dia = _dia(Encargo.cancelado_en)
    for d, monto in db.execute(
        select(dia, func.sum(Encargo.monto_retenido))
        .where(
            Encargo.sede_id == p.sede_id,
            Encargo.estado == "cancelado",
            Encargo.cancelado_en >= inicio,
            Encargo.cancelado_en < fin,
        )
        .group_by(dia)
    ).all():
        agregar(d, "Abono retenido por cancelación", DIVERSOS_INGRESO, monto)

    dia = _dia(EncargoAbono.fecha)
    for d, n, monto in db.execute(
        select(dia, func.count(), func.sum(EncargoAbono.monto))
        .join(Encargo, Encargo.id == EncargoAbono.encargo_id)
        .where(
            Encargo.sede_id == p.sede_id,
            EncargoAbono.estado == "vigente",
            EncargoAbono.fecha >= inicio,
            EncargoAbono.fecha < fin,
        )
        .group_by(dia)
    ).all():
        agregar(d, "Abonos de encargos (anticipos)", ANTICIPOS, monto, n)

    fecha_gasto = func.to_char(Gasto.fecha, "YYYY-MM-DD")
    for d, categoria, cuenta, n, monto in db.execute(
        select(
            fecha_gasto,
            CategoriaGasto.nombre,
            CategoriaGasto.cuenta_puc,
            func.count(),
            func.sum(Gasto.monto),
        )
        .join(CategoriaGasto, CategoriaGasto.id == Gasto.categoria_id)
        .where(
            Gasto.sede_id == p.sede_id,
            Gasto.fecha >= p.desde,
            Gasto.fecha <= p.hasta,
            Gasto.estado == "registrado",
        )
        .group_by(fecha_gasto, CategoriaGasto.nombre, CategoriaGasto.cuenta_puc)
    ).all():
        agregar(d, f"Gasto · {categoria}", cuenta, monto, n)

    dia = _dia(CajaMovimiento.fecha)
    for d, metodo, cuenta, monto in db.execute(
        select(dia, MetodoPago.nombre, MetodoPago.cuenta_puc, func.sum(CajaMovimiento.monto))
        .join(MetodoPago, MetodoPago.id == CajaMovimiento.metodo_pago_id)
        .where(
            CajaMovimiento.sede_id == p.sede_id,
            CajaMovimiento.fecha >= inicio,
            CajaMovimiento.fecha < fin,
            CajaMovimiento.tipo.in_(TIPOS_RECIBIDO),
            CajaMovimiento.monto > 0,
        )
        .group_by(dia, MetodoPago.nombre, MetodoPago.cuenta_puc)
    ).all():
        agregar(d, f"Dinero recibido · {metodo}", cuenta, monto)

    return sorted(filas, key=lambda f: (f["fecha"], f["cuenta"], f["concepto"]))


def reporte_puc(db: Session, p: Periodo) -> Reporte:
    filas = movimientos(db, p)
    por_cuenta: dict[str, int] = defaultdict(int)
    for f in filas:
        por_cuenta[f["cuenta"]] += f["monto"]
    return nuevo(
        db,
        p,
        "puc",
        "Movimientos con código PUC",
        [
            seccion(
                "Movimientos",
                [
                    col("fecha", "Fecha", "fecha"),
                    col("concepto", "Concepto"),
                    col("referencia", "Referencia"),
                    col("cuenta", "Cuenta PUC"),
                    col("monto", "Monto", "pesos"),
                ],
                filas,
            ),
            seccion(
                "Por cuenta",
                [col("cuenta", "Cuenta PUC"), col("monto", "Monto", "pesos")],
                [{"cuenta": c, "monto": m} for c, m in sorted(por_cuenta.items())],
            ),
        ],
    )
