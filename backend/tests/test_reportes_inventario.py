"""Reportes de inventario y utilidad de la fase 4 (#46). Valores calculados a mano."""

from datetime import date
from decimal import Decimal as D

from app.modules.reportes.inventario import inventario_valorizado, producido_vs_vendido
from app.modules.reportes.periodo import Periodo
from tests.conftest import SEDE_PRINCIPAL
from tests.fixtures_reportes import malteada, reporte, seccion, vendida
from tests.fixtures_ventas import API, lote, post

HOY = date(2026, 11, 10)


def _abrir(cliente, admin, reloj):
    reloj("2026-11-10T09:00:00-05:00")
    r = cliente.post(f"{API}/caja/abrir", headers=admin, json={"base_inicial": 100000})
    assert r.status_code == 201, r.text


def test_utilidad_por_producto(cliente, admin, carta, metodos, reloj):
    _abrir(cliente, admin, reloj)
    vendida(
        cliente,
        admin,
        {
            "tipo_servicio": "local",
            "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "2"}],
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 9000}],
        },
    )
    r = reporte(cliente, admin, "utilidad-productos", HOY, HOY)
    assert r.status_code == 200, r.text
    fila = seccion(r.json(), "Por producto")["filas"][0]
    # 2 pasteles a $4.500 con costo PEPS de $675 c/u: 9.000 − 1.350 = 7.650; margen 85 %.
    assert (fila["producto"], fila["ventas"], fila["costo"], fila["utilidad"]) == (
        "Pastel de pollo",
        9000,
        1350,
        7650,
    )
    assert fila["margen"] == "85.00"


def test_utilidad_resta_el_descuento_sobre_el_total(cliente, admin, carta, metodos, reloj):
    _abrir(cliente, admin, reloj)
    vendida(
        cliente,
        admin,
        malteada(carta, metodos, {"tipo": "valor", "valor": "1000", "motivo": "Amiga"}, 15000),
    )
    r = reporte(cliente, admin, "utilidad-productos", HOY, HOY).json()
    sec = seccion(r, "Por producto")
    assert sec["totales"]["ventas"] == 15000
    assert sec["totales"]["utilidad"] == 15000 - 4200


def test_valorizado_a_fecha_pasada(cliente, admin, db, ctx, reloj):
    harina = post(cliente, admin, "/insumos", {"nombre": "Harina valorizada", "unidad_base": "g"})
    reloj("2026-11-01T10:00:00-05:00")
    lote(db, ctx, "insumo", harina["id"], "10", "1000")
    reloj("2026-11-03T10:00:00-05:00")
    r = cliente.post(
        f"{API}/mermas",
        headers=admin,
        json={"tipo_item": "insumo", "item_id": harina["id"], "cantidad": "4", "motivo": "danado"},
    )
    assert r.status_code == 201, r.text

    def valor(corte):
        return sum(
            f.valor
            for f in inventario_valorizado(db, SEDE_PRINCIPAL, corte)
            if f.item == "Harina valorizada"
        )

    assert valor(date(2026, 10, 31)) == 0
    assert valor(date(2026, 11, 2)) == 10000
    assert valor(date(2026, 11, 3)) == 6000


def test_mermas_por_motivo(cliente, admin, carta, reloj):
    reloj("2026-11-10T10:00:00-05:00")
    for cantidad, motivo in (("2", "vencido"), ("1", "danado")):
        r = cliente.post(
            f"{API}/mermas",
            headers=admin,
            json={
                "tipo_item": "producto",
                "item_id": carta["pastel"]["id"],
                "cantidad": cantidad,
                "motivo": motivo,
            },
        )
        assert r.status_code == 201, r.text
    r = reporte(cliente, admin, "mermas", HOY, HOY).json()
    motivos = {f["motivo"]: f["costo"] for f in seccion(r, "Por motivo")["filas"]}
    assert motivos == {"Vencido": 1350, "Dañado": 675}
    assert seccion(r, "Por ítem")["totales"]["costo"] == 2025


def test_producido_contra_vendido(cliente, admin, carta, metodos, reloj, db):
    _abrir(cliente, admin, reloj)
    vendida(
        cliente,
        admin,
        {
            "tipo_servicio": "local",
            "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "3"}],
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 13500}],
        },
    )
    filas = {
        f.producto: (f.producido, f.vendido)
        for f in producido_vs_vendido(db, Periodo(sede_id=SEDE_PRINCIPAL, desde=HOY, hasta=HOY))
    }
    assert filas["Pastel de pollo"] == (D(0), D(3))


def test_produccion_ve_inventario_pero_no_utilidad(cliente, crear_usuario, login):
    produccion = login(crear_usuario("produccion", email="prod@zuquis.co"))
    assert reporte(cliente, produccion, "mermas", HOY, HOY).status_code == 200
    assert reporte(cliente, produccion, "inventario-valorizado", HOY, HOY).status_code == 200
    assert reporte(cliente, produccion, "utilidad-productos", HOY, HOY).status_code == 403
