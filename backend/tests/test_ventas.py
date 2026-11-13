"""Registro de ventas: carrito, pago mixto, propina, inventario y caja (#29)."""

import time
import uuid
from decimal import Decimal as D

from sqlalchemy import func, select

from app.modules.caja.models import CajaMovimiento
from app.modules.inventario.models import FaltanteInventario
from tests.fixtures_ventas import API, esperado, lote, post, stock, vender, venta_mockup

# --- El ejemplo del mockup ------------------------------------------------------------------


def test_venta_del_mockup_da_los_totales_al_peso(cliente, admin, carta, metodos, caja_abierta):
    r = vender(cliente, admin, venta_mockup(carta, metodos))
    assert r.status_code == 201, r.text
    v = r.json()
    assert (v["subtotal"], v["descuento_total"], v["total"], v["propina"], v["cobrado"]) == (
        49500,
        3000,
        46500,
        2000,
        48500,
    )
    assert v["descuento_motivo"] == "Cliente frecuente"
    assert [(i["producto"], i["cantidad"], i["subtotal"]) for i in v["items"]] == [
        ("Malteada de brownie", "1.0000", 21000),
        ("Soda frutos rojos", "1.0000", 12000),
        ("Pastel de pollo", "2.0000", 9000),
        ("Croissant de jamón y queso", "1.0000", 7500),
    ]
    assert v["items"][0]["modificadores"] == [
        {
            "modificador_id": carta["helado"]["id"],
            "nombre": "Bola de helado",
            "precio": 5000,
            "costo_total": 1600,
        }
    ]
    assert (v["items"][1]["nota"], v["items"][3]["nota"]) == ("Sin hielo", "Caliente")
    assert v["numero"] >= 1 and v["estado"] == "pagada"


def test_cada_item_guarda_su_costo_real(cliente, admin, carta, metodos, caja_abierta):
    v = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    # Malteada: 1 × $3.000 + 300 ml × $4 (la adición va aparte: 80 g × $20).
    assert [i["costo_total"] for i in v["items"]] == [4200, 1500, 1350, 2000]
    assert v["costo_total"] == 4200 + 1600 + 1500 + 1350 + 2000


def test_la_venta_descuenta_el_inventario(cliente, admin, carta, metodos, caja_abierta, db):
    vender(cliente, admin, venta_mockup(carta, metodos))
    assert stock(db, "producto", carta["pastel"]["id"]) == D("10")
    assert stock(db, "producto", carta["croissant"]["id"]) == D("7")
    assert stock(db, "insumo", carta["insumos"]["Leche venta"]) == D("9700")
    assert stock(db, "insumo", carta["insumos"]["Helado venta"]) == D("4920")
    assert stock(db, "insumo", carta["insumos"]["Jarabe venta"]) == D("1950")


def test_la_caja_recibe_venta_por_metodo_y_propina_aparte(
    cliente, admin, carta, metodos, caja_abierta, db
):
    v = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    assert esperado(cliente, admin) | {} == {
        **{n: 0 for n in metodos},
        "Efectivo": 100000 + 28500,
        "Nequi": 20000,
    }
    movs = db.execute(
        select(CajaMovimiento.tipo, CajaMovimiento.monto)
        .where(CajaMovimiento.referencia_id == uuid.UUID(v["id"]))
        .order_by(CajaMovimiento.tipo, CajaMovimiento.monto)
    ).all()
    # RN-15: la propina entra en su propio movimiento; la venta se reparte en orden de pago.
    assert [tuple(m) for m in movs] == [("propina", 2000), ("venta", 18000), ("venta", 28500)]


def test_cambio_en_efectivo_no_se_guarda_como_pago(cliente, admin, carta, metodos, caja_abierta):
    datos = venta_mockup(carta, metodos)
    datos["pagos"] = [{"metodo_pago_id": metodos["Efectivo"], "monto": 48500, "recibido": 50000}]
    v = vender(cliente, admin, datos).json()
    assert (v["pagos"][0]["recibido"], v["pagos"][0]["cambio"], v["cambio"]) == (50000, 1500, 1500)
    assert esperado(cliente, admin)["Efectivo"] == 100000 + 48500


# --- Reglas -----------------------------------------------------------------------------------


def test_los_pagos_deben_cubrir_exactamente_lo_cobrado(
    cliente, admin, carta, metodos, caja_abierta
):
    datos = venta_mockup(carta, metodos)
    datos["pagos"][1]["monto"] = 19000
    r = vender(cliente, admin, datos)
    assert (r.status_code, r.json()["codigo"]) == (422, "PAGOS_NO_CUADRAN")


def test_sin_caja_abierta_no_se_vende(cliente, admin, carta, metodos):
    r = vender(cliente, admin, venta_mockup(carta, metodos))
    assert (r.status_code, r.json()["codigo"]) == (409, "CAJA_CERRADA")


def test_sin_idempotency_key_no_se_vende(cliente, admin, carta, metodos, caja_abierta):
    r = cliente.post(f"{API}/ventas", headers=admin, json=venta_mockup(carta, metodos))
    assert (r.status_code, r.json()["codigo"]) == (400, "IDEMPOTENCIA_REQUERIDA")


def test_reintento_no_duplica_la_venta(cliente, admin, carta, metodos, caja_abierta, db):
    clave = str(uuid.uuid4())
    a = vender(cliente, admin, venta_mockup(carta, metodos), clave).json()
    b = vender(cliente, admin, venta_mockup(carta, metodos), clave).json()
    assert a["id"] == b["id"]
    assert stock(db, "producto", carta["pastel"]["id"]) == D("10")


def test_consecutivo_sin_saltos_ni_repetidos(cliente, admin, carta, metodos, caja_abierta):
    simple = {
        "tipo_servicio": "llevar",
        "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "1"}],
        "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 4500}],
    }
    a = vender(cliente, admin, simple).json()["numero"]
    b = vender(cliente, admin, simple).json()["numero"]
    assert b == a + 1


def test_si_falta_inventario_no_se_guarda_nada(cliente, admin, carta, metodos, caja_abierta, db):
    datos = venta_mockup(carta, metodos)
    datos["items"][3]["cantidad"] = "9"  # solo hay 8 croissants
    datos["pagos"] = [
        {"metodo_pago_id": metodos["Efectivo"], "monto": 49500 + 7500 * 8 - 3000 + 2000}
    ]
    r = vender(cliente, admin, datos)
    assert (r.status_code, r.json()["codigo"]) == (409, "STOCK_INSUFICIENTE")
    assert "Croissant" in r.json()["mensaje"]
    # Nada se movió: ni el inventario de los ítems anteriores ni la caja.
    assert stock(db, "producto", carta["pastel"]["id"]) == D("12")
    assert stock(db, "insumo", carta["insumos"]["Leche venta"]) == D("10000")
    assert esperado(cliente, admin)["Efectivo"] == 100000
    assert cliente.get(f"{API}/ventas", headers=admin).json()["total"] == 0


def test_venta_sin_stock_permitida_deja_faltante(cliente, admin, carta, metodos, caja_abierta, db):
    cliente.patch(f"{API}/configuracion", headers=admin, json={"permitir_venta_sin_stock": True})
    unico = post(
        cliente,
        admin,
        "/productos",
        {
            "categoria_id": carta["pastel"]["categoria_id"],
            "nombre": "Empanada venta",
            "tipo": "lote",
            "precio": 3000,
        },
    )
    r = vender(
        cliente,
        admin,
        {
            "tipo_servicio": "local",
            "items": [{"producto_id": unico["id"], "cantidad": "3"}],
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 9000}],
        },
    )
    # Sin ningún lote: todo queda como faltante, con stock en 0 (nunca negativo).
    assert r.status_code == 201, r.text
    assert stock(db, "producto", unico["id"]) == D("0")
    faltante = db.scalar(
        select(func.sum(FaltanteInventario.cantidad_pendiente)).where(
            FaltanteInventario.item_id == uuid.UUID(unico["id"]),
            FaltanteInventario.estado == "abierto",
        )
    )
    assert faltante == D("3")


def test_vender_3_con_1_disponible_deja_0_y_faltante_de_2(
    cliente, admin, carta, metodos, caja_abierta, db, ctx
):
    cliente.patch(f"{API}/configuracion", headers=admin, json={"permitir_venta_sin_stock": True})
    p = post(
        cliente,
        admin,
        "/productos",
        {
            "categoria_id": carta["pastel"]["categoria_id"],
            "nombre": "Palito de queso venta",
            "tipo": "lote",
            "precio": 3300,
        },
    )
    lote(db, ctx, "producto", p["id"], "1", "1000")
    r = vender(
        cliente,
        admin,
        {
            "tipo_servicio": "local",
            "items": [{"producto_id": p["id"], "cantidad": "3"}],
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 9900}],
        },
    )
    assert r.status_code == 201, r.text
    assert stock(db, "producto", p["id"]) == D("0")
    pendiente = db.scalar(
        select(func.sum(FaltanteInventario.cantidad_pendiente)).where(
            FaltanteInventario.item_id == uuid.UUID(p["id"]), FaltanteInventario.estado == "abierto"
        )
    )
    assert pendiente == D("2")
    # El costo del ítem incluye lo faltante estimado al último costo ($1.000 c/u).
    assert r.json()["items"][0]["costo_total"] == 3000


def test_producto_agotado_no_se_vende(cliente, admin, carta, metodos, caja_abierta):
    cliente.patch(
        f"{API}/productos/{carta['soda']['id']}", headers=admin, json={"disponible": False}
    )
    r = vender(
        cliente,
        admin,
        {
            "tipo_servicio": "local",
            "items": [{"producto_id": carta["soda"]["id"], "cantidad": "1"}],
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 12000}],
        },
    )
    assert (r.status_code, r.json()["codigo"]) == (409, "PRODUCTO_AGOTADO")


def test_adicion_que_no_aplica_al_producto(cliente, admin, carta, metodos, caja_abierta):
    r = vender(
        cliente,
        admin,
        {
            "tipo_servicio": "local",
            "items": [
                {
                    "producto_id": carta["soda"]["id"],
                    "cantidad": "1",
                    "modificador_ids": [carta["helado"]["id"]],
                }
            ],
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 17000}],
        },
    )
    assert (r.status_code, r.json()["codigo"]) == (422, "ADICION_NO_APLICA")


def test_listar_ventas_por_caja(cliente, admin, carta, metodos, caja_abierta):
    v = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    r = cliente.get(f"{API}/ventas", headers=admin, params={"caja_sesion_id": v["caja_sesion_id"]})
    assert r.status_code == 200, r.text
    assert [x["id"] for x in r.json()["items"]] == [v["id"]]
    assert cliente.get(f"{API}/ventas/{v['id']}", headers=admin).json()["numero"] == v["numero"]


def test_el_cajero_vende_a_su_nombre(cliente, carta, metodos, crear_usuario, login):
    cajero = login(crear_usuario("cajero", nombre="Cajero de turno"))
    cliente.post(f"{API}/caja/abrir", headers=cajero, json={"base_inicial": 0})
    datos = venta_mockup(carta, metodos, descuento=None)
    datos["pagos"][0]["monto"] += 3000
    v = vender(cliente, cajero, datos).json()
    assert v["cajero"] == "Cajero de turno"


def test_venta_de_10_items_en_menos_de_un_segundo(cliente, admin, carta, metodos, caja_abierta):
    items = [
        {
            "producto_id": carta["malteada"]["id"],
            "cantidad": "1",
            "modificador_ids": [carta["helado"]["id"]],
        }
        for _ in range(5)
    ] + [{"producto_id": carta["pastel"]["id"], "cantidad": "1"} for _ in range(5)]
    datos = {
        "tipo_servicio": "local",
        "items": items,
        "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 21000 * 5 + 4500 * 5}],
    }
    inicio = time.perf_counter()
    r = vender(cliente, admin, datos)
    assert r.status_code == 201, r.text
    assert time.perf_counter() - inicio < 1.0
