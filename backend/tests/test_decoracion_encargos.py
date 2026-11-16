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
