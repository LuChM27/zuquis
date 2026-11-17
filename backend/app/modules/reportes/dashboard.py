"""Dashboard de Inicio (RF-41, mockup docs/mockups/dashboard.png).

Periodo: desde el día local en que se abrió la caja abierta de la sede hasta hoy; sin caja
abierta, solo hoy. Las cifras salen de ``cifras`` y por eso coinciden con el reporte de ventas
del mismo rango.
"""

import uuid
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.modules.caja.service import caja_abierta
from app.modules.clientes.models import Cliente
from app.modules.configuracion.service import valor
from app.modules.encargos.models import Encargo, EncargoAbono
from app.modules.inventario.consultas import alertas
from app.modules.inventario.schemas import Alerta
from app.modules.reportes import cifras
from app.modules.reportes.cifras import FilaVentas
from app.modules.reportes.periodo import Periodo
from app.modules.reportes.tablas_inventario import porcentaje
from app.shared.fechas import a_local, hoy, zona


class EncargoHoy(BaseModel):
    id: uuid.UUID
    numero: int
    descripcion: str
    cliente: str
    hora: datetime
    saldo: int
    estado: str


class Dashboard(BaseModel):
    fecha: date
    caja_abierta_desde: datetime | None
    datos_ejemplo: bool
    ventas: int
    n_ventas: int
    gastos: int
    n_gastos: int
    ganancia: int
    ticket_promedio: int
    por_hora: list[FilaVentas]
    por_metodo: list[FilaVentas]
    porcentaje_metodo: dict[str, Decimal]
    mas_vendidos: list[FilaVentas]
    encargos_hoy: list[EncargoHoy]
    alertas: list[Alerta]


def _encargos_de_hoy(db: Session, sede_id: uuid.UUID, dia: date) -> list[EncargoHoy]:
    inicio = datetime.combine(dia, time(), tzinfo=zona())
    abonado = (
        select(EncargoAbono.encargo_id, func.sum(EncargoAbono.monto).label("monto"))
        .where(EncargoAbono.estado == "vigente")
        .group_by(EncargoAbono.encargo_id)
        .subquery()
    )
    filas = db.execute(
        select(
            Encargo.id,
            Encargo.numero,
            Encargo.descripcion,
            Cliente.nombre,
            Encargo.fecha_entrega,
            Encargo.total - func.coalesce(abonado.c.monto, 0),
            Encargo.estado,
        )
        .join(Cliente, Cliente.id == Encargo.cliente_id)
        .outerjoin(abonado, abonado.c.encargo_id == Encargo.id)
        .where(
            Encargo.sede_id == sede_id,
            Encargo.fecha_entrega >= inicio,
            Encargo.fecha_entrega < inicio + timedelta(days=1),
            Encargo.estado.not_in(("cancelado", "entregado")),
        )
        .order_by(Encargo.fecha_entrega)
    ).all()
    return [
        EncargoHoy(id=i, numero=n, descripcion=d, cliente=c, hora=h, saldo=int(s), estado=e)
        for i, n, d, c, h, s, e in filas
    ]


def dashboard(db: Session, ctx: Contexto) -> Dashboard:
    hoy_ = hoy()
    sesion = caja_abierta(db, ctx.sede_id)
    desde = min(a_local(sesion.abierta_en).date(), hoy_) if sesion else hoy_
    p = Periodo(sede_id=ctx.sede_id, desde=desde, hasta=hoy_)
    t = cifras.totales(db, p)
    cobradas = t.n_ventas - t.n_cortesias
    ticket = (
        int((Decimal(t.ventas) / cobradas).quantize(Decimal(1), ROUND_HALF_UP)) if cobradas else 0
    )
    por_metodo = cifras.ventas_por(db, p, "metodo")
    cobrado = sum(f.ventas for f in por_metodo)
    productos = cifras.ventas_por(db, p, "producto")
    return Dashboard(
        fecha=hoy_,
        caja_abierta_desde=sesion.abierta_en if sesion else None,
        datos_ejemplo=bool(valor(db, ctx.sede_id, "datos_ejemplo")),
        ventas=t.ventas,
        n_ventas=t.n_ventas,
        gastos=t.gastos,
        n_gastos=t.n_gastos,
        ganancia=t.ganancia_estimada,
        ticket_promedio=ticket,
        por_hora=cifras.ventas_por(db, p, "hora"),
        por_metodo=por_metodo,
        porcentaje_metodo={f.etiqueta: porcentaje(f.ventas, cobrado) for f in por_metodo},
        mas_vendidos=sorted(productos, key=lambda f: (-f.unidades, f.etiqueta))[:5],
        encargos_hoy=_encargos_de_hoy(db, ctx.sede_id, hoy_),
        alertas=alertas(db, ctx),
    )
