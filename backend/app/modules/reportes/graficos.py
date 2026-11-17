"""Datos de la galería de 14 gráficos (pestaña "Gráficos" de Reportes), por grupo.

Regla: las cifras salen de ``cifras``, ``dinero`` e ``inventario`` (las mismas de las tablas).
Aquí solo se agregan las consultas que no existen en otro lado (por pagar, encargos, clientes
y cajeros) y se da la forma que necesita cada gráfico.
"""

import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any, Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.auth.models import Usuario
from app.modules.caja.models import CajaArqueo, CajaSesion
from app.modules.carta.models import Producto
from app.modules.clientes.models import Cliente
from app.modules.compras.models import Compra, PagoCompra
from app.modules.encargos.models import Encargo, EncargoAbono
from app.modules.reportes import cifras, dinero, inventario
from app.modules.reportes.cifras import _del_periodo, _suma, es_cortesia, local
from app.modules.reportes.periodo import Periodo
from app.modules.reportes.tablas_inventario import porcentaje
from app.modules.ventas.models import Venta
from app.shared.errores import SinPermiso
from app.shared.fechas import zona

Grupo = Literal["ganancia", "ventas", "productos", "gastos", "encargos", "cajeros"]
GRUPOS: tuple[str, ...] = ("ganancia", "ventas", "productos", "gastos", "encargos", "cajeros")


def _fin_del_dia(d: date) -> datetime:
    return datetime.combine(d + timedelta(days=1), time(), tzinfo=zona())


# --- Consultas propias de la galería --------------------------------------------------------


def por_pagar(db: Session, sede_id: uuid.UUID, corte: date) -> list[dict]:
    """Compras a crédito no anuladas, hechas hasta el corte, con su saldo."""
    pagos = (
        select(PagoCompra.compra_id, func.sum(PagoCompra.monto).label("pagado"))
        .group_by(PagoCompra.compra_id)
        .subquery()
    )
    filas = db.execute(
        select(
            Compra.fecha, Compra.fecha_limite_pago, Compra.total - func.coalesce(pagos.c.pagado, 0)
        )
        .outerjoin(pagos, pagos.c.compra_id == Compra.id)
        .where(
            Compra.sede_id == sede_id,
            Compra.estado_pago == "por_pagar",
            ~Compra.anulada,
            Compra.fecha <= corte,
        )
    ).all()
    return [{"fecha": f, "fecha_limite_pago": lim, "saldo": int(s)} for f, lim, s in filas]


def _por_pagar_agrupado(filas: list[dict], corte: date) -> dict[str, dict[str, int]]:
    con = {"vencidas": 0, "esta_semana": 0, "proximas": 0}
    sin = {"d0_15": 0, "d16_30": 0, "d30_mas": 0}
    for f in filas:
        limite = f["fecha_limite_pago"]
        if limite:
            dias = (limite - corte).days
            con["vencidas" if dias < 0 else "esta_semana" if dias <= 6 else "proximas"] += f[
                "saldo"
            ]
        else:
            edad = (corte - f["fecha"]).days
            sin["d0_15" if edad <= 15 else "d16_30" if edad <= 30 else "d30_mas"] += f["saldo"]
    return {"con_fecha": con, "sin_fecha": sin}


def encargos_por_semana(db: Session, p: Periodo) -> list[dict]:
    inicio, fin = p.limites()
    semanas: dict[str, dict[str, int]] = defaultdict(lambda: {"entregados": 0, "cancelados": 0})
    for columna, clave in (
        (Encargo.entregado_en, "entregados"),
        (Encargo.cancelado_en, "cancelados"),
    ):
        semana = func.to_char(local(columna), 'IYYY-"W"IW')
        estado = "entregado" if clave == "entregados" else "cancelado"
        for s, n in db.execute(
            select(semana, func.count())
            .where(
                Encargo.sede_id == p.sede_id,
                Encargo.estado == estado,
                columna >= inicio,
                columna < fin,
            )
            .group_by(semana)
        ).all():
            semanas[s][clave] = int(n)
    return [{"semana": s} | v for s, v in sorted(semanas.items())]


def abonos_sin_entregar(db: Session, sede_id: uuid.UUID, corte: date) -> int:
    """Abonos vigentes recibidos hasta el corte de encargos que a esa fecha no estaban
    entregados ni cancelados (anticipos, cuenta 2805)."""
    fin = _fin_del_dia(corte)
    return int(
        db.scalar(
            select(_suma(EncargoAbono.monto))
            .join(Encargo, Encargo.id == EncargoAbono.encargo_id)
            .where(
                Encargo.sede_id == sede_id,
                EncargoAbono.estado == "vigente",
                EncargoAbono.fecha < fin,
                or_(Encargo.entregado_en.is_(None), Encargo.entregado_en >= fin),
                or_(Encargo.cancelado_en.is_(None), Encargo.cancelado_en >= fin),
            )
        )
    )


def clientes_top(db: Session, p: Periodo, n: int = 10) -> list[dict]:
    """Clientes con más encargos entregados en el rango y lo que suman."""
    inicio, fin = p.limites()
    filas = db.execute(
        select(Cliente.nombre, func.count(), func.sum(Encargo.total))
        .join(Cliente, Cliente.id == Encargo.cliente_id)
        .where(
            Encargo.sede_id == p.sede_id,
            Encargo.estado == "entregado",
            Encargo.entregado_en >= inicio,
            Encargo.entregado_en < fin,
        )
        .group_by(Cliente.id, Cliente.nombre)
        .order_by(func.count().desc(), func.sum(Encargo.total).desc())
        .limit(n)
    ).all()
    return [{"cliente": c, "encargos": int(k), "total": int(t)} for c, k, t in filas]


def por_cajero(db: Session, p: Periodo) -> list[dict]:
    """Por cajero: vendido, descuentos (sin cortesías), cortesías y la diferencia de los
    cierres que contó (quien cerró la caja)."""
    cortesia = es_cortesia()
    inicio, fin = p.limites()
    filas: dict[uuid.UUID, dict] = {}

    def fila(usuario_id: uuid.UUID, nombre: str) -> dict:
        return filas.setdefault(
            usuario_id,
            {
                "cajero": nombre,
                "vendido": 0,
                "descuentos": 0,
                "cortesias": 0,
                "diferencia_cierres": 0,
            },
        )

    for uid, nombre, v, d, c in db.execute(
        select(
            Usuario.id,
            Usuario.nombre,
            _suma(Venta.total),
            func.coalesce(func.sum(Venta.descuento_total).filter(~cortesia), 0),
            func.count().filter(cortesia),
        )
        .join(Usuario, Usuario.id == Venta.usuario_id)
        .where(*_del_periodo(p))
        .group_by(Usuario.id, Usuario.nombre)
    ).all():
        fila(uid, nombre).update(vendido=int(v), descuentos=int(d), cortesias=int(c))
    for uid, nombre, dif in db.execute(
        select(Usuario.id, Usuario.nombre, func.sum(CajaArqueo.diferencia))
        .join(CajaSesion, CajaSesion.id == CajaArqueo.caja_sesion_id)
        .join(Usuario, Usuario.id == CajaSesion.cerrada_por)
        .where(
            CajaSesion.sede_id == p.sede_id,
            CajaSesion.cerrada_en >= inicio,
            CajaSesion.cerrada_en < fin,
        )
        .group_by(Usuario.id, Usuario.nombre)
    ).all():
        fila(uid, nombre)["diferencia_cierres"] = int(dif or 0)
    return sorted(filas.values(), key=lambda f: -f["vendido"])


def _menos_vendidos(db: Session, p: Periodo, vendidos: dict[str, Any], n: int = 10) -> list[dict]:
    """Los productos activos de la carta con menos unidades (incluye los que no se vendieron)."""
    activos = db.execute(
        select(Producto.id, Producto.nombre).where(Producto.sede_id == p.sede_id, Producto.activo)
    ).all()
    filas = [{"producto": nombre, "unidades": vendidos.get(str(i), 0)} for i, nombre in activos]
    return sorted(filas, key=lambda f: (f["unidades"], f["producto"]))[:n]


# --- Grupos --------------------------------------------------------------------------------


def _ganancia(db: Session, p: Periodo) -> dict:
    t = cifras.totales(db, p)
    regalado = t.costo_cortesias
    flujo: dict[str, dict[str, int]] = defaultdict(
        lambda: {"entra_negocio": 0, "entra_dueno": 0, "sale": 0}
    )
    for f in dinero.flujo(db, p):
        dia = flujo[f.dia]
        dia["entra_dueno" if f.titular == "Dueño" else "entra_negocio"] += f.entra
        dia["sale"] += f.sale
    return {
        "cascada": {
            "ventas": t.ventas,
            "costo_insumos": t.costo_insumos,
            "regalado": regalado,
            "gastos": t.gastos,
            "mermas": t.mermas,
            "ingresos_cancelacion": t.ingresos_cancelacion,
            "utilidad": t.utilidad,
        },
        "costo_pct": [
            {
                "semana": f.clave,
                "ventas": f.ventas,
                "costo": f.costo,
                "pct": porcentaje(f.costo, f.ventas),
            }
            for f in cifras.ventas_por(db, p, "semana")
        ],
        "flujo": [{"dia": d} | v for d, v in sorted(flujo.items())],
    }


def _ventas(db: Session, p: Periodo) -> dict:
    anterior = Periodo(
        sede_id=p.sede_id,
        desde=p.desde - timedelta(days=p.dias),
        hasta=p.desde - timedelta(days=1),
    )
    calor = []
    for f in cifras.ventas_por(db, p, "dia_semana_hora"):
        dow, hora = f.clave.split("-")
        calor.append({"dow": int(dow), "hora": int(hora), "ventas": f.ventas})
    categorias = cifras.ventas_por(db, p, "categoria")
    total = sum(f.ventas for f in categorias)
    return {
        "dia_a_dia": [
            {"dia": f.clave, "ventas": f.ventas} for f in cifras.ventas_por(db, p, "dia")
        ],
        "anterior": [
            {"dia": f.clave, "ventas": f.ventas} for f in cifras.ventas_por(db, anterior, "dia")
        ],
        "calor": calor,
        "categorias": [
            {"categoria": f.etiqueta, "ventas": f.ventas, "pct": porcentaje(f.ventas, total)}
            for f in categorias
        ],
    }


def _productos(db: Session, p: Periodo, completo: bool) -> dict:
    datos: dict[str, Any] = {
        "producido_vendido": [f.model_dump() for f in inventario.producido_vs_vendido(db, p)]
    }
    if completo:
        productos = cifras.ventas_por(db, p, "producto")
        mas = sorted(productos, key=lambda f: (-f.unidades, f.etiqueta))[:10]
        datos["mas_vendidos"] = [
            {"producto": f.etiqueta, "unidades": f.unidades, "ventas": f.ventas} for f in mas
        ]
        datos["menos_vendidos"] = _menos_vendidos(db, p, {f.clave: f.unidades for f in productos})
    return datos


def _gastos(db: Session, p: Periodo, completo: bool) -> dict:
    mermas = inventario.mermas_por(db, p)
    por_motivo: dict[str, int] = defaultdict(int)
    por_item: dict[str, int] = defaultdict(int)
    for m in mermas:
        por_motivo[m.motivo] += m.costo
        por_item[m.item] += m.costo
    datos: dict[str, Any] = {
        "mermas": {
            "por_motivo": [{"motivo": k, "costo": v} for k, v in por_motivo.items()],
            "por_item": [
                {"item": k, "costo": v} for k, v in sorted(por_item.items(), key=lambda x: -x[1])
            ],
        }
    }
    if completo:
        datos["por_categoria_mes"] = [
            {"mes": g.mes, "categoria": g.categoria, "monto": g.monto}
            for g in dinero.gastos_por(db, p)
        ]
        datos["por_pagar"] = _por_pagar_agrupado(por_pagar(db, p.sede_id, p.hasta), p.hasta)
    return datos


def _encargos(db: Session, p: Periodo) -> dict:
    return {
        "por_semana": encargos_por_semana(db, p),
        "abonos_sin_entregar": abonos_sin_entregar(db, p.sede_id, p.hasta),
        "clientes_top": clientes_top(db, p),
    }


def grupo(db: Session, p: Periodo, g: str, permisos: frozenset[str]) -> dict[str, Any]:
    """Datos de un grupo. Con solo ``reportes.ver_inventario`` (producción) se entregan los
    gráficos de inventario: producido contra vendido y mermas."""
    completo = "reportes.ver" in permisos
    if not completo and not (
        "reportes.ver_inventario" in permisos and g in ("productos", "gastos")
    ):
        raise SinPermiso("reportes.ver")
    if g == "ganancia":
        return _ganancia(db, p)
    if g == "ventas":
        return _ventas(db, p)
    if g == "productos":
        return _productos(db, p, completo)
    if g == "gastos":
        return _gastos(db, p, completo)
    if g == "encargos":
        return _encargos(db, p)
    return {"por_cajero": por_cajero(db, p)}
