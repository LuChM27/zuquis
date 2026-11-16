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
