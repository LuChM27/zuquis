"""Decoración en encargos: referencia y valor por ítem, línea propia en la venta y gastos de
materiales ligados al encargo."""

from decimal import Decimal as D

import pytest

from tests.conftest import SEDE_PRINCIPAL
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


# --- Pendientes de la revisión ---------------------------------------------------------------


MENSAJE_INCOMPLETA = "La decoración necesita referencia y valor."


@pytest.mark.parametrize(
    "extra",
    [
        {"decoracion": "Letras doradas"},
        {"decoracion_precio": 15000},
        {"decoracion": "   ", "decoracion_precio": 15000},
        {"decoracion": "Letras doradas", "decoracion_precio": 0},
    ],
)
def test_decoracion_incompleta_dice_por_que(cliente, admin, cliente_a, extra):
    item = {"descripcion": "Torta 1 lb", "cantidad": "1", "precio": 90000} | extra
    r = crear_encargo(cliente, admin, con_items(cliente_a["id"], item))
    assert r.status_code == 422, r.text
    assert r.json()["mensaje"] == MENSAJE_INCOMPLETA
    assert [e["mensaje"] for e in r.json()["detalle"]["errores"]] == [MENSAJE_INCOMPLETA]


def test_gasto_sobre_encargo_de_otra_sede_no_existe(
    cliente, decorado, metodos, crear_usuario, login, db
):
    from app.modules.configuracion.models import Sede

    otra = Sede(nombre="Sede Norte")
    db.add(otra)
    db.commit()
    headers = login(crear_usuario("admin", sede_id=otra.id), sede_id=otra.id)
    r = gasto_decoracion(cliente, headers, decorado, metodos["Efectivo"])
    assert r.status_code == 404, r.text


def test_cajero_tampoco_registra_gastos_de_los_duenos(
    cliente, decorado, metodos, crear_usuario, login
):
    cajero = login(crear_usuario("cajero"))
    r = gasto_decoracion(cliente, cajero, decorado, metodos["Efectivo"], fuente="duenos")
    assert r.status_code == 403, r.text


def test_anular_la_venta_y_reentregar_da_el_mismo_total(
    cliente, admin, decorado, metodos, caja_abierta
):
    venta = entregar_y_ver_venta(cliente, admin, decorado, 115000, metodos["Efectivo"])
    r = cliente.post(
        f"{API}/ventas/{venta['id']}/anular", headers=admin, json={"motivo": "Error de cobro"}
    )
    assert r.status_code == 200, r.text
    r = entregar(
        cliente, admin, decorado, [{"metodo_pago_id": metodos["Efectivo"], "monto": 115000}]
    )
    assert r.status_code == 200, r.text
    otra = cliente.get(f"{API}/ventas/{r.json()['venta_id']}", headers=admin).json()
    assert otra["total"] == venta["total"] == 115000
    assert [i["producto"] for i in otra["items"]] == [i["producto"] for i in venta["items"]]


def test_categoria_de_decoracion_no_se_renombra_ni_desactiva(cliente, admin):
    cats = cliente.get(f"{API}/categorias-gasto", headers=admin).json()
    deco = next(c for c in cats if c["nombre"] == "Materiales de decoración")
    assert deco["sistema"] is True
    assert all(c["sistema"] is False for c in cats if c["id"] != deco["id"])
    for cambio in ({"nombre": "Decoración"}, {"activa": False}):
        r = cliente.patch(f"{API}/categorias-gasto/{deco['id']}", headers=admin, json=cambio)
        assert (r.status_code, r.json()["codigo"]) == (409, "CATEGORIA_DEL_SISTEMA"), r.text
    r = cliente.patch(
        f"{API}/categorias-gasto/{deco['id']}", headers=admin, json={"cuenta_puc": "5140"}
    )
    assert r.status_code == 200, r.text


def test_el_resumen_agrupa_la_decoracion(cliente, admin, cliente_a, metodos, caja_abierta):
    for referencia, valor in (("Letras doradas", 20000), ("Topper de foto", 15000)):
        item = DECORADA | {"decoracion": referencia, "decoracion_precio": valor}
        e = crear_encargo(cliente, admin, con_items(cliente_a["id"], item)).json()
        entregar_y_ver_venta(cliente, admin, e, e["total"], metodos["Efectivo"])
    productos = cliente.get(f"{API}/ventas/resumen", headers=admin).json()["productos"]
    deco = [p for p in productos if p["producto"].startswith("Decoración")]
    assert [(p["producto"], p["valor"]) for p in deco] == [("Decoración", 35000)]


def test_solo_con_gastos_no_se_ve_el_encargo(
    cliente, admin, decorado, metodos, crear_usuario, login
):
    rol = cliente.post(
        f"{API}/roles", headers=admin, json={"nombre": "Solo gastos", "permisos": ["gastos.crear"]}
    ).json()
    usuario = crear_usuario("produccion")
    cliente.patch(
        f"{API}/usuarios/{usuario.id}",
        headers=admin,
        json={"roles": [{"rol_id": rol["id"], "sede_id": str(SEDE_PRINCIPAL)}]},
    )
    headers = login(usuario)
    r = gasto_decoracion(cliente, headers, decorado, metodos["Nequi"], fuente="banco")
    assert r.status_code == 403, r.text


def test_cajero_solo_ve_sus_gastos_de_decoracion(
    cliente, admin, decorado, metodos, caja_abierta, crear_usuario, login
):
    gasto_decoracion(cliente, admin, decorado, metodos["Nequi"], 7000, fuente="banco")
    cajero = login(crear_usuario("cajero"))
    gasto_decoracion(cliente, cajero, decorado, metodos["Efectivo"], 2000)
    visto = cliente.get(f"{API}/encargos/{decorado['id']}", headers=cajero).json()
    assert [g["monto"] for g in visto["gastos_decoracion"]] == [2000]
    # El resumen sí cuenta todo lo gastado: es la cuenta del encargo, no el detalle de cada gasto.
    assert visto["gasto_decoracion"] == 9000
    completo = cliente.get(f"{API}/encargos/{decorado['id']}", headers=admin).json()
    assert [g["monto"] for g in completo["gastos_decoracion"]] == [7000, 2000]
