"""Cifras de dinero: gastos, flujo de caja, cierres, descuentos, domicilios, propinas y
cancelaciones. Igual que ``cifras``, es la única fuente de estos números y todo se agrega en SQL.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import case, func, literal, select
from sqlalchemy.orm import Session, aliased

from app.modules.auth.models import Usuario
from app.modules.caja.models import CajaArqueo, CajaMovimiento, CajaSesion
from app.modules.clientes.models import Cliente
from app.modules.compras.models import Compra, PagoCompra
from app.modules.configuracion.models import MetodoPago
from app.modules.domicilios.models import Domiciliario, Domicilio
from app.modules.encargos.models import Encargo
from app.modules.gastos.models import CategoriaGasto, Gasto
from app.modules.reportes.cifras import _del_periodo, _suma, es_cortesia, local
from app.modules.reportes.periodo import Periodo
from app.modules.ventas.models import Venta

TITULARES = {"negocio": "Negocio", "dueno": "Dueño"}


class FilaGasto(BaseModel):
    categoria: str
    cuenta_puc: str | None
    fuente: str
    mes: str
    monto: int
    n: int


def _gastos_vigentes(p: Periodo) -> list:
    return [
        Gasto.sede_id == p.sede_id,
        Gasto.fecha >= p.desde,
        Gasto.fecha <= p.hasta,
        Gasto.estado == "registrado",
    ]


def gastos_por(db: Session, p: Periodo) -> list[FilaGasto]:
    """Gastos registrados (sin anulados) por categoría, fuente y mes, por ``gastos.fecha``."""
    mes = func.to_char(Gasto.fecha, "YYYY-MM")
    filas = db.execute(
        select(
            CategoriaGasto.nombre,
            CategoriaGasto.cuenta_puc,
            Gasto.fuente,
            mes,
            func.sum(Gasto.monto),
            func.count(),
        )
        .join(CategoriaGasto, CategoriaGasto.id == Gasto.categoria_id)
        .where(*_gastos_vigentes(p))
        .group_by(CategoriaGasto.nombre, CategoriaGasto.cuenta_puc, Gasto.fuente, mes)
        .order_by(mes, func.sum(Gasto.monto).desc())
    ).all()
    return [
        FilaGasto(categoria=c, cuenta_puc=puc, fuente=f, mes=m, monto=int(t), n=int(n))
        for c, puc, f, m, t, n in filas
    ]


class FilaFlujo(BaseModel):
    dia: str
    tipo: str
    metodo: str
    titular: str
    en_caja: bool
    entra: int
    sale: int


def flujo(db: Session, p: Periodo) -> list[FilaFlujo]:
    """Todo el dinero que entra y sale: los movimientos de caja (con signo: + entra, − sale)
    más lo pagado fuera de caja (gastos de banco o dueños y pagos a proveedores sin caja).
    Lo que ya generó un movimiento de caja no se vuelve a sumar."""
    inicio, fin = p.limites()
    dia_mov = func.to_char(local(CajaMovimiento.fecha), "YYYY-MM-DD")
    monto = CajaMovimiento.monto
    en_caja = (
        select(
            dia_mov.label("dia"),
            CajaMovimiento.tipo.label("tipo"),
            CajaMovimiento.metodo_pago_id.label("metodo_id"),
            literal(True).label("en_caja"),
            _suma(case((monto > 0, monto), else_=0)).label("entra"),
            _suma(case((monto < 0, -monto), else_=0)).label("sale"),
        )
        .where(
            CajaMovimiento.sede_id == p.sede_id,
            CajaMovimiento.fecha >= inicio,
            CajaMovimiento.fecha < fin,
        )
        .group_by(dia_mov, CajaMovimiento.tipo, CajaMovimiento.metodo_pago_id)
    )
    dia_gasto = func.to_char(Gasto.fecha, "YYYY-MM-DD")
    gastos_fuera = (
        select(
            dia_gasto,
            literal("gasto"),
            Gasto.metodo_pago_id,
            literal(False),
            literal(0),
            func.sum(Gasto.monto),
        )
        .where(*_gastos_vigentes(p), Gasto.fuente != "caja")
        .group_by(dia_gasto, Gasto.metodo_pago_id)
    )
    dia_pago = func.to_char(local(PagoCompra.fecha), "YYYY-MM-DD")
    pagos_fuera = (
        select(
            dia_pago,
            literal("pago_compra"),
            PagoCompra.metodo_pago_id,
            literal(False),
            literal(0),
            func.sum(PagoCompra.monto),
        )
        .join(Compra, Compra.id == PagoCompra.compra_id)
        .where(
            Compra.sede_id == p.sede_id,
            ~Compra.anulada,
            PagoCompra.fecha >= inicio,
            PagoCompra.fecha < fin,
            PagoCompra.caja_sesion_id.is_(None),
        )
        .group_by(dia_pago, PagoCompra.metodo_pago_id)
    )
    todo = en_caja.union_all(gastos_fuera, pagos_fuera).subquery()
    filas = db.execute(
        select(
            todo.c.dia,
            todo.c.tipo,
            MetodoPago.nombre,
            MetodoPago.titular,
            todo.c.en_caja,
            todo.c.entra,
            todo.c.sale,
        )
        .join(MetodoPago, MetodoPago.id == todo.c.metodo_id)
        .order_by(todo.c.dia, todo.c.tipo, MetodoPago.orden)
    ).all()
    return [
        FilaFlujo(
            dia=d,
            tipo=t,
            metodo=m,
            titular=TITULARES.get(tit, tit),
            en_caja=bool(c),
            entra=int(e),
            sale=int(s),
        )
        for d, t, m, tit, c, e, s in filas
    ]


class FilaCierre(BaseModel):
    sesion_id: uuid.UUID
    abierta_en: datetime
    cerrada_en: datetime
    cerrada_por: str
    metodo: str
    esperado: int
    contado: int
    diferencia: int


def cierres(db: Session, p: Periodo) -> list[FilaCierre]:
    """Arqueos de las cajas cerradas en el rango; la diferencia es de quien cerró (contó)."""
    inicio, fin = p.limites()
    filtro = [
        CajaSesion.sede_id == p.sede_id,
        CajaSesion.estado == "cerrada",
        CajaSesion.cerrada_en >= inicio,
        CajaSesion.cerrada_en < fin,
    ]
    if p.caja_sesion_id:
        filtro.append(CajaSesion.id == p.caja_sesion_id)
    filas = db.execute(
        select(
            CajaSesion.id,
            CajaSesion.abierta_en,
            CajaSesion.cerrada_en,
            Usuario.nombre,
            MetodoPago.nombre,
            CajaArqueo.esperado,
            CajaArqueo.contado,
            CajaArqueo.diferencia,
        )
        .join(CajaArqueo, CajaArqueo.caja_sesion_id == CajaSesion.id)
        .join(MetodoPago, MetodoPago.id == CajaArqueo.metodo_pago_id)
        .join(Usuario, Usuario.id == CajaSesion.cerrada_por)
        .where(*filtro)
        .order_by(CajaSesion.cerrada_en, MetodoPago.orden)
    ).all()
    return [
        FilaCierre(
            sesion_id=s,
            abierta_en=a,
            cerrada_en=c,
            cerrada_por=u,
            metodo=m,
            esperado=e,
            contado=k,
            diferencia=d,
        )
        for s, a, c, u, m, e, k, d in filas
    ]


def descuentos_cortesias(db: Session, p: Periodo) -> list[dict]:
    """Ventas con descuento o cortesía: quién vendió, quién autorizó y cuánto."""
    autorizo = aliased(Usuario)
    filas = db.execute(
        select(
            Venta.numero,
            Venta.fecha,
            Usuario.nombre,
            Venta.descuento_motivo,
            autorizo.nombre,
            Venta.descuento_total,
            es_cortesia(),
            Venta.costo_total,
        )
        .join(Usuario, Usuario.id == Venta.usuario_id)
        .outerjoin(autorizo, autorizo.id == Venta.descuento_autorizado_por)
        .where(*_del_periodo(p), Venta.descuento_total > 0)
        .order_by(Venta.fecha)
    ).all()
    return [
        {
            "venta": n,
            "fecha": f,
            "cajero": cajero,
            "motivo": motivo,
            "autorizo": aut,
            "descuento": int(d),
            "cortesia": bool(c),
            "costo_cortesia": int(k) if c else 0,
        }
        for n, f, cajero, motivo, aut, d, c, k in filas
    ]


def domicilios_por(db: Session, p: Periodo) -> list[dict]:
    """Domicilios de ventas pagadas por domiciliario (dinero de terceros, RN-18)."""
    filas = db.execute(
        select(Domiciliario.nombre, func.count(), func.sum(Domicilio.valor))
        .join(Venta, Venta.id == Domicilio.venta_id)
        .join(Domiciliario, Domiciliario.id == Domicilio.domiciliario_id)
        .where(*_del_periodo(p))
        .group_by(Domiciliario.nombre)
        .order_by(func.sum(Domicilio.valor).desc())
    ).all()
    return [{"domiciliario": d, "n": int(n), "valor": int(v)} for d, n, v in filas]


def propinas_por_dia(db: Session, p: Periodo) -> list[dict]:
    dia = func.to_char(local(Venta.fecha), "YYYY-MM-DD")
    filas = db.execute(
        select(dia, func.sum(Venta.propina))
        .where(*_del_periodo(p), Venta.propina > 0)
        .group_by(dia)
        .order_by(dia)
    ).all()
    return [{"dia": d, "propinas": int(v)} for d, v in filas]


def cancelaciones(db: Session, p: Periodo) -> list[dict]:
    """Encargos cancelados en el rango: lo devuelto y lo retenido (ingreso, RN-22)."""
    inicio, fin = p.limites()
    filas = db.execute(
        select(
            Encargo.numero,
            Cliente.nombre,
            Encargo.cancelado_en,
            Encargo.monto_devuelto,
            Encargo.monto_retenido,
            Encargo.motivo_cancelacion,
        )
        .join(Cliente, Cliente.id == Encargo.cliente_id)
        .where(
            Encargo.sede_id == p.sede_id,
            Encargo.estado == "cancelado",
            Encargo.cancelado_en >= inicio,
            Encargo.cancelado_en < fin,
        )
        .order_by(Encargo.cancelado_en)
    ).all()
    return [
        {
            "encargo": n,
            "cliente": c,
            "fecha": f,
            "devuelto": int(d),
            "retenido": int(r),
            "motivo": m,
        }
        for n, c, f, d, r, m in filas
    ]
