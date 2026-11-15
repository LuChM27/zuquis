"""Consulta de ventas: buscar por número y resumen del día (qué se vendió y cómo se cobró)."""

import pytest

from tests.fixtures_ventas import API, vender, venta_mockup

pytestmark = pytest.mark.usefixtures("caja_abierta")


@pytest.fixture
def dia(cliente, admin, carta, metodos):
    mockup = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    simple = vender(
        cliente,
        admin,
        {
            "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "1"}],
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 4500}],
        },
    ).json()
    anulada = vender(
        cliente,
        admin,
        {
            "items": [{"producto_id": carta["soda"]["id"], "cantidad": "1"}],
            "pagos": [{"metodo_pago_id": metodos["Nequi"], "monto": 12000}],
        },
    ).json()
    r = cliente.post(
        f"{API}/ventas/{anulada['id']}/anular", headers=admin, json={"motivo": "Error de cobro"}
    )
    assert r.status_code == 200, r.text
    return {"mockup": mockup, "simple": simple, "anulada": anulada}


def test_buscar_una_venta_por_numero(cliente, admin, dia):
    numero = dia["simple"]["numero"]
    r = cliente.get(f"{API}/ventas", headers=admin, params={"numero": numero})
    assert r.status_code == 200, r.text
    assert [v["id"] for v in r.json()["items"]] == [dia["simple"]["id"]]


def test_resumen_del_dia(cliente, admin, dia):
    r = cliente.get(f"{API}/ventas/resumen", headers=admin)
    assert r.status_code == 200, r.text
    resumen = r.json()
    assert (resumen["ventas"], resumen["anuladas"]) == (2, 1)
    assert resumen["total"] == 46500 + 4500
    assert resumen["descuentos"] == 3000
    assert resumen["propinas"] == 2000
    assert {m["metodo"]: m["monto"] for m in resumen["por_metodo"]} == {
        "Efectivo": 28500 + 4500,
        "Nequi": 20000,
    }
    # Lo vendido por producto, sin la venta anulada, del que más vendió al que menos.
    assert [(p["producto"], p["cantidad"], p["valor"]) for p in resumen["productos"]] == [
        ("Malteada de brownie", "1.0000", 21000),
        ("Pastel de pollo", "3.0000", 13500),
        ("Soda frutos rojos", "1.0000", 12000),
        ("Croissant de jamón y queso", "1.0000", 7500),
    ]


def test_el_resumen_respeta_el_rango_de_fechas(cliente, admin, dia):
    r = cliente.get(
        f"{API}/ventas/resumen",
        headers=admin,
        params={"desde": "2020-01-01", "hasta": "2020-01-02"},
    )
    assert r.json()["ventas"] == 0
    assert r.json()["productos"] == []
