"""Decoración en encargos: referencia y valor por ítem, línea propia en la venta y gastos de
materiales ligados al encargo."""

from decimal import Decimal as D

import pytest

from tests.fixtures_encargos import (
    abonar,
    alistar,
    cancelar,
    con_clave,
    crear_encargo,
    entregar,
    torta,
)
from tests.fixtures_ventas import API, stock

DECORADA = {
    "descripcion": "Torta 1 lb",
    "cantidad": "1",
    "precio": 90000,
    "decoracion": "Letras doradas",
    "decoracion_precio": 20000,
}


def con_items(cliente_id, *items):
    return torta(cliente_id, descripcion=None, items=list(items))


def editar_items(cliente, headers, encargo, *items):
    return cliente.patch(
        f"{API}/encargos/{encargo['id']}", headers=headers, json={"items": list(items)}
    )


# --- Ítems con decoración -------------------------------------------------------------------


def test_decoracion_suma_al_total_una_vez_por_item(cliente, admin, cliente_a, carta):
    item = {
        "producto_id": carta["pastel"]["id"],
        "cantidad": "2",
        "precio": 4000,
        "decoracion": "Letras doradas",
        "decoracion_precio": 15000,
    }
    r = crear_encargo(cliente, admin, con_items(cliente_a["id"], item))
    assert r.status_code == 201, r.text
    e = r.json()
    assert e["total"] == 23000
    i = e["items"][0]
    assert (i["decoracion"], i["decoracion_precio"], i["subtotal"]) == (
        "Letras doradas",
        15000,
        8000,
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"decoracion": "Letras doradas"},
        {"decoracion_precio": 15000},
        {"decoracion": "   ", "decoracion_precio": 15000},
        {"decoracion": "Letras doradas", "decoracion_precio": 0},
    ],
)
def test_decoracion_necesita_referencia_y_valor(cliente, admin, cliente_a, extra):
    item = {"descripcion": "Torta 1 lb", "cantidad": "1", "precio": 90000} | extra
    r = crear_encargo(cliente, admin, con_items(cliente_a["id"], item))
    assert r.status_code == 422, r.text


def test_item_sin_decoracion_sigue_igual(cliente, admin, cliente_a):
    e = crear_encargo(cliente, admin, torta(cliente_a["id"])).json()
    assert (e["items"][0]["decoracion"], e["items"][0]["decoracion_precio"]) == (None, None)
    assert e["total"] == 90000


def test_editar_quita_la_decoracion_y_respeta_lo_abonado(
    cliente, admin, cliente_a, metodos, caja_abierta
):
    e = crear_encargo(cliente, admin, con_items(cliente_a["id"], DECORADA)).json()
    assert e["total"] == 110000
    assert abonar(cliente, admin, e, 100000, metodos["Efectivo"]).status_code == 201
    sin_decoracion = {k: v for k, v in DECORADA.items() if not k.startswith("decoracion")}
    r = editar_items(cliente, admin, e, sin_decoracion)
    assert r.status_code == 422, r.text
    assert r.json()["codigo"] == "ABONO_EXCEDE_SALDO"
    r = editar_items(cliente, admin, e, DECORADA | {"decoracion_precio": 30000})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 120000


def test_categoria_de_decoracion_sembrada(cliente, admin):
    r = cliente.get(f"{API}/categorias-gasto", headers=admin).json()
    assert {"nombre": "Materiales de decoración", "cuenta_puc": "5195"} in [
        {"nombre": c["nombre"], "cuenta_puc": c["cuenta_puc"]} for c in r
    ]


# --- Entrega: la decoración es una línea propia de la venta ---------------------------------


def entregar_y_ver_venta(cliente, headers, encargo, monto, metodo):
    alistar(cliente, headers, encargo)
    r = entregar(cliente, headers, encargo, [{"metodo_pago_id": metodo, "monto": monto}])
    assert r.status_code == 200, r.text
    return cliente.get(f"{API}/ventas/{r.json()['venta_id']}", headers=headers).json()


def test_entregar_agrega_linea_de_decoracion_sin_inventario(
    cliente, admin, cliente_a, carta, metodos, caja_abierta, db
):
    pastel = {
        "producto_id": carta["pastel"]["id"],
        "cantidad": "10",
        "precio": 4000,
        "decoracion": "Topper de foto",
        "decoracion_precio": 12000,
    }
    caja = {"descripcion": "Caja", "cantidad": "1", "precio": 5000}
    e = crear_encargo(cliente, admin, con_items(cliente_a["id"], pastel, caja)).json()
    assert e["total"] == 57000
    venta = entregar_y_ver_venta(cliente, admin, e, 57000, metodos["Efectivo"])
    assert stock(db, "producto", carta["pastel"]["id"]) == D("2")
    assert venta["total"] == 57000
    lineas = [(i["producto"], i["precio_unitario"], i["costo_total"]) for i in venta["items"]]
    assert lineas[1:] == [("Decoración: Topper de foto", 12000, 0), ("Caja", 5000, 0)]
    assert lineas[0][1] == 4000


def test_referencia_larga_se_recorta_en_la_venta(cliente, admin, cliente_a, metodos, caja_abierta):
    item = DECORADA | {"decoracion": "x" * 200}
    e = crear_encargo(cliente, admin, con_items(cliente_a["id"], item)).json()
    venta = entregar_y_ver_venta(cliente, admin, e, 110000, metodos["Efectivo"])
    assert len(venta["items"][1]["producto"]) == 200
    assert venta["items"][1]["producto"].startswith("Decoración: xxx")


# --- Gastos de materiales de decoración ------------------------------------------------------


def gasto_decoracion(cliente, headers, encargo, metodo, monto=9000, fuente="caja"):
    return cliente.post(
        f"{API}/encargos/{encargo['id']}/gastos",
        headers=con_clave(headers),
        json={
            "descripcion": "Fondant y topper",
            "monto": monto,
            "metodo_pago_id": metodo,
            "fuente": fuente,
        },
    )


@pytest.fixture
def decorado(cliente, admin, cliente_a):
    item = DECORADA | {"decoracion_precio": 25000}
    return crear_encargo(cliente, admin, con_items(cliente_a["id"], item)).json()


def test_gasto_de_decoracion_queda_ligado_y_en_gastos(
    cliente, admin, decorado, metodos, caja_abierta
):
    r = gasto_decoracion(cliente, admin, decorado, metodos["Efectivo"])
    assert r.status_code == 201, r.text
    e = r.json()
    assert (e["decoracion_cobrada"], e["gasto_decoracion"]) == (25000, 9000)
    assert [(g["descripcion"], g["monto"], g["estado"]) for g in e["gastos_decoracion"]] == [
        ("Fondant y topper", 9000, "registrado")
    ]
    gastos = cliente.get(f"{API}/gastos", headers=admin).json()["items"]
    g = next(g for g in gastos if g["id"] == e["gastos_decoracion"][0]["id"])
    assert (g["categoria"], g["encargo_id"], g["encargo_numero"]) == (
        "Materiales de decoración",
        decorado["id"],
        decorado["numero"],
    )
    movs = cliente.get(f"{API}/caja/actual/movimientos", headers=admin).json()
    assert ("gasto", -9000) in [(m["tipo"], m["monto"]) for m in movs]


def test_gasto_anulado_no_cuenta(cliente, admin, decorado, metodos, caja_abierta):
    e = gasto_decoracion(cliente, admin, decorado, metodos["Efectivo"]).json()
    gasto_id = e["gastos_decoracion"][0]["id"]
    r = cliente.post(f"{API}/gastos/{gasto_id}/anular", headers=admin, json={"motivo": "Error"})
    assert r.status_code == 200, r.text
    e = cliente.get(f"{API}/encargos/{decorado['id']}", headers=admin).json()
    assert e["gasto_decoracion"] == 0
    assert [g["estado"] for g in e["gastos_decoracion"]] == ["anulado"]


def test_gasto_en_encargo_entregado_o_cancelado(
    cliente, admin, cliente_a, decorado, metodos, caja_abierta
):
    gasto_decoracion(cliente, admin, decorado, metodos["Efectivo"])
    assert cancelar(cliente, admin, decorado).status_code == 200
    r = gasto_decoracion(cliente, admin, decorado, metodos["Efectivo"], 3000)
    assert r.status_code == 201, r.text
    assert [g["estado"] for g in r.json()["gastos_decoracion"]] == ["registrado", "registrado"]
    assert r.json()["gasto_decoracion"] == 12000

    otro = crear_encargo(cliente, admin, con_items(cliente_a["id"], DECORADA)).json()
    entregar_y_ver_venta(cliente, admin, otro, 110000, metodos["Efectivo"])
    assert gasto_decoracion(cliente, admin, otro, metodos["Efectivo"]).status_code == 201


def test_cajero_solo_desde_la_caja(cliente, decorado, metodos, crear_usuario, login):
    cajero = login(crear_usuario("cajero"))
    cliente.post(f"{API}/caja/abrir", headers=cajero, json={"base_inicial": 50000})
    r = gasto_decoracion(cliente, cajero, decorado, metodos["Nequi"], fuente="banco")
    assert r.status_code == 403, r.text
    r = gasto_decoracion(cliente, cajero, decorado, metodos["Efectivo"])
    assert r.status_code == 201, r.text
