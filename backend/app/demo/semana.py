"""Semana de ejemplo (fase 4, #49): la misma que usa el caso de control de reportes.

Se arma con los servicios reales del sistema, hecho por hecho y con la hora fijada en cada uno
(``fijar_ahora``), para que los reportes la lean igual que una semana de verdad. Los resultados
esperados están calculados a mano en backend/tests/control/fase4.md.

Lunes 9 a domingo 15 de noviembre de 2026 (o la semana que empiece en ``lunes``).
"""

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal as D
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.core.permisos import CATALOGO
from app.modules.caja import cierre
from app.modules.caja import service as caja
from app.modules.caja.schemas import CerrarCaja, ContadoMetodo
from app.modules.carta import service as carta
from app.modules.carta.models import Categoria
from app.modules.carta.schemas import (
    CategoriaCrear,
    ProductoCrear,
    RecetaEntrada,
    RecetaItemEntrada,
)
from app.modules.clientes import service as clientes
from app.modules.clientes.schemas import ClienteCrear
from app.modules.compras import service as compras
from app.modules.compras.schemas import CompraCrear, CompraItemEntrada
from app.modules.configuracion.models import Configuracion, MetodoPago
from app.modules.domicilios import service as domicilios
from app.modules.domicilios.schemas import DomiciliarioCrear, DomicilioEntrada, LiquidarEntrada
from app.modules.encargos import service as encargos
from app.modules.encargos.schemas import (
    AbonoEntrada,
    CancelacionEntrada,
    EncargoCrear,
    EntregaEntrada,
)
from app.modules.encargos.schemas import ItemEntrada as ItemEncargo
from app.modules.gastos import service as gastos
from app.modules.gastos.models import CategoriaGasto
from app.modules.gastos.schemas import GastoCrear
from app.modules.inventario import operaciones
from app.modules.inventario import service as insumos
from app.modules.inventario.schemas import InsumoCrear, MermaCrear
from app.modules.produccion import service as produccion
from app.modules.produccion.schemas import ProduccionCrear
from app.modules.ventas import service as ventas
from app.modules.ventas.models import Venta
from app.modules.ventas.schemas import DescuentoEntrada, ItemEntrada, PagoEntrada, VentaCrear
from app.shared.fechas import fijar_ahora, zona


def contexto(usuario_id: uuid.UUID, sede_id: uuid.UUID) -> Contexto:
    """Contexto con todos los permisos (lo que haría el administrador)."""
    return Contexto(
        usuario_id=usuario_id, sede_id=sede_id, permisos=frozenset(p.clave for p in CATALOGO)
    )


def generar_semana(db: Session, ctx: Contexto, lunes: date) -> dict[str, Any]:
    db.info["usuario_id"] = ctx.usuario_id

    def a_las(dia: int, hora: int, minuto: int = 0) -> datetime:
        momento = datetime.combine(lunes + timedelta(days=dia), time(hora, minuto), tzinfo=zona())
        fijar_ahora(momento)
        return momento

    metodos = {
        m.nombre: m.id
        for m in db.scalars(select(MetodoPago).where(MetodoPago.sede_id == ctx.sede_id))
    }
    efectivo, nequi, bancolombia = metodos["Efectivo"], metodos["Nequi"], metodos["Bancolombia"]
    categorias_gasto = {
        c.nombre: c.id
        for c in db.scalars(select(CategoriaGasto).where(CategoriaGasto.sede_id == ctx.sede_id))
    }

    def categoria(nombre: str) -> uuid.UUID:
        existente = db.scalar(
            select(Categoria).where(Categoria.sede_id == ctx.sede_id, Categoria.nombre == nombre)
        )
        return (
            existente.id
            if existente
            else carta.crear_categoria(db, ctx, CategoriaCrear(nombre=nombre)).id
        )

    try:
        # --- Carta e insumos (lunes temprano) ------------------------------------------------
        a_las(0, 7)
        harina = insumos.crear_insumo(
            db, ctx, InsumoCrear(nombre="Harina de trigo", unidad_base="g")
        )
        leche = insumos.crear_insumo(db, ctx, InsumoCrear(nombre="Leche entera", unidad_base="ml"))
        pan = carta.crear_producto(
            db,
            ctx,
            ProductoCrear(
                categoria_id=categoria("Panadería"), nombre="Pan de bono", tipo="lote", precio=2000
            ),
        )
        cafe = carta.crear_producto(
            db,
            ctx,
            ProductoCrear(
                categoria_id=categoria("Bebidas"),
                nombre="Café con leche",
                tipo="preparado",
                precio=5000,
            ),
        )
        carta.guardar_receta(
            db,
            ctx,
            RecetaEntrada(
                rendimiento=D(1), items=[RecetaItemEntrada(insumo_id=harina.id, cantidad=D(100))]
            ),
            producto_id=pan.id,
        )
        carta.guardar_receta(
            db,
            ctx,
            RecetaEntrada(
                rendimiento=D(1), items=[RecetaItemEntrada(insumo_id=leche.id, cantidad=D(200))]
            ),
            producto_id=cafe.id,
        )
        carlos = domicilios.crear_domiciliario(db, ctx, DomiciliarioCrear(nombre="Carlos"))
        ana = clientes.crear(db, ctx, ClienteCrear(nombre="Ana Gómez", telefono="3001112233"))
        beto = clientes.crear(db, ctx, ClienteCrear(nombre="Beto Ruiz", telefono="3004445566"))

        def compra(estado: str, insumo, cantidad: int, costo: int, **extra):
            return compras.crear_compra(
                db,
                ctx,
                CompraCrear(
                    estado_pago=estado,
                    items=[
                        CompraItemEntrada(
                            insumo_id=insumo.id, cantidad=D(cantidad), costo_total=costo
                        )
                    ],
                    **extra,
                ),
            )

        def vender(*items: tuple[Any, int], pagos=(), **extra):
            return ventas.crear(
                db,
                ctx,
                VentaCrear(
                    items=[ItemEntrada(producto_id=p.id, cantidad=D(c)) for p, c in items],
                    pagos=[PagoEntrada(metodo_pago_id=m, monto=v) for m, v in pagos],
                    **extra,
                ),
            )

        def abrir(dia: int):
            a_las(dia, 8)
            caja.abrir(db, ctx, 100000)

        def cerrar(dia: int, faltante: int = 0):
            a_las(dia, 20)
            vista = cierre.vista_previa(db, ctx)
            contado = [
                ContadoMetodo(
                    metodo_pago_id=a.metodo_pago_id,
                    contado=a.esperado - (faltante if a.es_efectivo else 0),
                )
                for a in vista.arqueo
            ]
            observacion = f"Faltaron ${faltante}" if faltante else None
            cierre.cerrar(db, ctx, CerrarCaja(contado=contado, observacion=observacion))

        # --- Lunes ---------------------------------------------------------------------------
        abrir(0)
        a_las(0, 9)
        compra("contado", harina, 3000, 9000, metodo_pago_id=efectivo)  # 3 $/g, fuera de caja
        compra("por_pagar", leche, 20000, 60000)  # 3 $/ml, sin fecha límite
        a_las(0, 10)
        produccion.crear(db, ctx, ProduccionCrear(producto_id=pan.id, cantidad_producida=D(20)))
        a_las(0, 11)
        vender((pan, 3), pagos=[(efectivo, 6000)])
        a_las(0, 16)
        vender((cafe, 2), pagos=[(nequi, 11000)], propina=1000)
        cerrar(0)

        # --- Martes --------------------------------------------------------------------------
        abrir(1)
        a_las(1, 9)
        gastos.crear(
            db,
            ctx,
            GastoCrear(
                categoria_id=categorias_gasto["Arriendo del local"],
                descripcion="Arriendo de noviembre",
                monto=500000,
                metodo_pago_id=bancolombia,
                fuente="banco",
            ),
        )
        a_las(1, 12)
        vender(
            (pan, 5),
            pagos=[(efectivo, 9000)],
            descuento=DescuentoEntrada(tipo="valor", valor=D(1000), motivo="Cliente frecuente"),
        )
        a_las(1, 17)
        vender(
            (cafe, 1),
            descuento=DescuentoEntrada(tipo="porcentaje", valor=D(100), motivo="Cumpleaños"),
        )
        a_las(1, 18)
        anulada = vender((pan, 2), pagos=[(efectivo, 4000)])
        ventas.anular(db, ctx, anulada.id, "Se cobró dos veces")
        cerrar(1)

        # --- Miércoles -----------------------------------------------------------------------
        abrir(2)
        a_las(2, 9)
        compra(
            "por_pagar",
            harina,
            10000,
            40000,  # 4 $/g
            fecha_limite_pago=lunes + timedelta(days=4),
        )
        a_las(2, 11)
        e1 = encargos.crear(
            db,
            ctx,
            EncargoCrear(
                cliente_id=ana.id,
                fecha_entrega=datetime.combine(lunes + timedelta(days=4), time(15), tzinfo=zona()),
                items=[
                    ItemEncargo(descripcion="Torta de chocolate 2 lb", cantidad=D(1), precio=50000)
                ],
            ),
        )
        encargos.abonar(db, ctx, e1.id, AbonoEntrada(monto=20000, metodo_pago_id=efectivo))
        a_las(2, 13)
        vender(
            (pan, 4),
            pagos=[(efectivo, 11000)],
            tipo_servicio="domicilio",
            valor_domicilio=3000,
            domicilio=DomicilioEntrada(domiciliario_id=carlos.id, direccion="Calle 10 # 4-20"),
        )
        a_las(2, 19)
        domicilios.liquidar(db, ctx, LiquidarEntrada(domiciliario_id=carlos.id))
        cerrar(2)

        # --- Jueves --------------------------------------------------------------------------
        abrir(3)
        a_las(3, 9)
        e2 = encargos.crear(
            db,
            ctx,
            EncargoCrear(
                cliente_id=beto.id,
                fecha_entrega=datetime.combine(lunes + timedelta(days=5), time(10), tzinfo=zona()),
                items=[
                    ItemEncargo(descripcion="Postre de tres leches", cantidad=D(1), precio=30000)
                ],
            ),
        )
        encargos.abonar(db, ctx, e2.id, AbonoEntrada(monto=10000, metodo_pago_id=nequi))
        a_las(3, 10)
        produccion.crear(db, ctx, ProduccionCrear(producto_id=pan.id, cantidad_producida=D(20)))
        a_las(3, 12)
        gastos.crear(
            db,
            ctx,
            GastoCrear(
                categoria_id=categorias_gasto["Aseo y cafetería"],
                descripcion="Bolsas y servilletas",
                monto=12000,
                metodo_pago_id=efectivo,
                fuente="caja",
            ),
        )
        a_las(3, 15)
        vender((pan, 6), pagos=[(efectivo, 12000)])
        a_las(3, 18)
        encargos.cancelar(
            db,
            ctx,
            e2.id,
            CancelacionEntrada(
                decision="devuelve_parcial", monto_devuelto=4000, motivo="Cambió de planes"
            ),
        )
        cerrar(3, faltante=2000)

        # --- Viernes -------------------------------------------------------------------------
        abrir(4)
        a_las(4, 10)
        papeleria = gastos.crear(
            db,
            ctx,
            GastoCrear(
                categoria_id=categorias_gasto["Papelería"],
                descripcion="Talonarios",
                monto=8000,
                metodo_pago_id=efectivo,
                fuente="caja",
            ),
        )
        gastos.anular(db, ctx, papeleria.id, "Registrado por error")
        a_las(4, 11)
        vender((pan, 4), pagos=[(bancolombia, 8000)])
        a_las(4, 14)
        for estado in ("en_produccion", "listo"):
            encargos.cambiar_estado(db, ctx, e1.id, estado)
        a_las(4, 15)
        encargos.entregar(
            db,
            ctx,
            e1.id,
            EntregaEntrada(pagos=[PagoEntrada(metodo_pago_id=efectivo, monto=30000)]),
        )
        cerrar(4)

        # --- Sábado --------------------------------------------------------------------------
        abrir(5)
        a_las(5, 10)
        vender((cafe, 3), pagos=[(efectivo, 15000)])
        a_las(5, 19)
        operaciones.registrar_merma(
            db,
            ctx,
            MermaCrear(tipo_item="producto", item_id=pan.id, cantidad=D(2), motivo="vencido"),
        )
        operaciones.registrar_merma(
            db,
            ctx,
            MermaCrear(tipo_item="insumo", item_id=harina.id, cantidad=D(500), motivo="danado"),
        )
        cerrar(5)
        db.flush()
    finally:
        fijar_ahora(None)
    return {"pan": pan.id, "cafe": cafe.id, "harina": harina.id, "leche": leche.id}


class SedeConVentas(Exception):
    """La semilla de ejemplo es solo para una sede sin ventas."""


def sembrar_demo(db: Session, usuario_id: uuid.UUID, sede_id: uuid.UUID, lunes: date) -> None:
    """Carga la semana de ejemplo y marca la sede con "Datos de ejemplo" (lo muestra Inicio)."""
    if db.scalar(select(func.count()).select_from(Venta).where(Venta.sede_id == sede_id)):
        raise SedeConVentas(
            "La sede ya tiene ventas; la semilla de ejemplo es solo para una base vacía."
        )
    generar_semana(db, contexto(usuario_id, sede_id), lunes)
    fila = db.scalar(
        select(Configuracion).where(
            Configuracion.sede_id == sede_id, Configuracion.clave == "datos_ejemplo"
        )
    )
    if fila:
        fila.valor = {"v": True}
    else:
        db.add(Configuracion(sede_id=sede_id, clave="datos_ejemplo", valor={"v": True}))
