"""Domicilios y liquidación al domiciliario (#40, RF-13, RF-19, RN-18)."""

import pytest

from tests.fixtures_encargos import cerrar_cuadrada
from tests.fixtures_ventas import API, esperado, post, vender

pytestmark = pytest.mark.usefixtures("caja_abierta")


def a_domicilio(carta, metodos, domiciliario, valor=4000, metodo="Efectivo", **extra):
    """Un pastel de pollo ($4.500) a domicilio."""
    return {
        "tipo_servicio": "domicilio",
        "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "1"}],
        "valor_domicilio": valor,
        "domicilio": {
            "domiciliario_id": domiciliario["id"],
            "direccion": "Cra 10 # 5-20",
            "telefono": "300 123 4567",
            "contacto": "Doña Marta",
        },
        "pagos": [{"metodo_pago_id": metodos[metodo], "monto": 4500 + valor}],
    } | extra


def liquidacion(cliente, headers):
    return cliente.get(f"{API}/caja/actual/domicilios", headers=headers).json()


def liquidar(cliente, headers, domiciliario, **extra):
    return cliente.post(
        f"{API}/caja/liquidar-domicilios",
        headers=headers,
        json={"domiciliario_id": domiciliario["id"]} | extra,
    )


def test_vender_a_domicilio_registra_el_domicilio(cliente, admin, carta, metodos, domiciliario):
    venta = vender(cliente, admin, a_domicilio(carta, metodos, domiciliario)).json()
    (d,) = cliente.get(f"{API}/domicilios", headers=admin).json()
    assert (d["venta_numero"], d["valor"], d["total_venta"]) == (venta["numero"], 4000, 4500)
    assert (d["cliente"], d["direccion"], d["telefono"]) == (
        "Doña Marta",
        "Cra 10 # 5-20",
        "3001234567",
    )
    assert (d["domiciliario"], d["estado"], d["liquidado_en"]) == ("Carlos", "pendiente", None)


def test_una_venta_a_domicilio_exige_direccion_y_domiciliario(
    cliente, admin, carta, metodos, domiciliario
):
    datos = a_domicilio(carta, metodos, domiciliario)
    del datos["domicilio"]
    assert vender(cliente, admin, datos).status_code == 422
    en_local = a_domicilio(carta, metodos, domiciliario, valor=0) | {"tipo_servicio": "local"}
    assert vender(cliente, admin, en_local).status_code == 422


def test_el_valor_del_domicilio_no_cuenta_como_venta(cliente, admin, carta, metodos, domiciliario):
    vender(cliente, admin, a_domicilio(carta, metodos, domiciliario))
    resumen = cliente.get(f"{API}/ventas/resumen", headers=admin).json()
    assert (resumen["total"], resumen["domicilios"]) == (4500, 4000)
    turno = cliente.get(f"{API}/caja/actual/cierre", headers=admin).json()["resumen"]
    assert turno["ventas"] == 4500


def test_cambiar_estado_y_reasignar(cliente, admin, carta, metodos, domiciliario):
    vender(cliente, admin, a_domicilio(carta, metodos, domiciliario))
    (d,) = cliente.get(f"{API}/domicilios", headers=admin).json()
    otro = post(cliente, admin, "/domiciliarios", {"nombre": "Diana"})
    r = cliente.patch(
        f"{API}/domicilios/{d['id']}/estado",
        headers=admin,
        json={"estado": "en_camino", "domiciliario_id": otro["id"]},
    )
    assert r.status_code == 200, r.text
    assert (r.json()["estado"], r.json()["domiciliario"]) == ("en_camino", "Diana")
    filtrados = cliente.get(
        f"{API}/domicilios", headers=admin, params={"estado": "entregado"}
    ).json()
    assert filtrados == []


def test_ejemplo_del_mockup_cuatro_domicilios_16000(cliente, admin, carta, metodos, domiciliario):
    """4 domicilios, $16.000 cobrados ⇒ $16.000 entregados; el efectivo no cambia neto."""
    antes = esperado(cliente, admin)["Efectivo"]
    for _ in range(4):
        assert vender(cliente, admin, a_domicilio(carta, metodos, domiciliario)).status_code == 201
    turno = liquidacion(cliente, admin)
    assert (turno["domicilios"], turno["cobrado"], turno["pendiente"]) == (4, 16000, 16000)
    assert esperado(cliente, admin)["Efectivo"] == antes + 4 * 4500 + 16000

    r = liquidar(cliente, admin, domiciliario)
    assert r.status_code == 200, r.text
    assert (r.json()["entregado"], r.json()["pendiente"]) == (16000, 0)
    assert esperado(cliente, admin)["Efectivo"] == antes + 4 * 4500

    vista = cliente.get(f"{API}/caja/actual/cierre", headers=admin).json()
    efectivo = dict((x["concepto"], x["monto"]) for x in vista["efectivo"])
    assert efectivo["Domicilios cobrados"] == 16000
    assert efectivo["Entregado al domiciliario"] == -16000
    assert vista["resumen"]["domicilios_entregados"] == 16000
    assert vista["domicilios"]["domiciliarios"] == [
        {
            "domiciliario_id": domiciliario["id"],
            "domiciliario": "Carlos",
            "domicilios": 4,
            "cobrado": 16000,
            "entregado": 16000,
            "pendiente": 0,
        }
    ]
    assert all(d["liquidado_en"] for d in cliente.get(f"{API}/domicilios", headers=admin).json())


def test_sin_liquidar_no_se_cierra_la_caja(cliente, admin, carta, metodos, domiciliario):
    vender(cliente, admin, a_domicilio(carta, metodos, domiciliario))
    vista = cliente.get(f"{API}/caja/actual/cierre", headers=admin).json()
    assert vista["domicilios_sin_liquidar"] == 1
    r = cliente.post(
        f"{API}/caja/cerrar",
        headers=admin,
        json={
            "contado": [
                {"metodo_pago_id": a["metodo_pago_id"], "contado": a["esperado"]}
                for a in vista["arqueo"]
            ]
        },
    )
    assert (r.status_code, r.json()["codigo"]) == (409, "DOMICILIOS_SIN_LIQUIDAR")

    assert liquidar(cliente, admin, domiciliario).status_code == 200
    assert cerrar_cuadrada(cliente, admin)["Efectivo"] == 100000 + 4500


def test_liquidar_dos_veces_no_paga_doble(cliente, admin, carta, metodos, domiciliario):
    vender(cliente, admin, a_domicilio(carta, metodos, domiciliario))
    assert liquidar(cliente, admin, domiciliario).status_code == 200
    r = liquidar(cliente, admin, domiciliario)
    assert (r.status_code, r.json()["codigo"]) == (409, "NADA_QUE_LIQUIDAR")


def test_liquidar_con_un_monto_desactualizado_avisa(cliente, admin, carta, metodos, domiciliario):
    vender(cliente, admin, a_domicilio(carta, metodos, domiciliario))
    r = liquidar(cliente, admin, domiciliario, monto=3000)
    assert (r.status_code, r.json()["codigo"]) == (409, "LIQUIDACION_CAMBIO")
    assert r.json()["detalle"]["pendiente"] == 4000


def test_domicilio_pagado_por_nequi_se_entrega_en_efectivo(
    cliente, admin, carta, metodos, domiciliario
):
    vender(cliente, admin, a_domicilio(carta, metodos, domiciliario, metodo="Nequi"))
    liquidar(cliente, admin, domiciliario)
    caja = esperado(cliente, admin)
    assert (caja["Efectivo"], caja["Nequi"]) == (100000 - 4000, 8500)


def test_anular_la_venta_cancela_el_domicilio(cliente, admin, carta, metodos, domiciliario):
    venta = vender(cliente, admin, a_domicilio(carta, metodos, domiciliario)).json()
    r = cliente.post(
        f"{API}/ventas/{venta['id']}/anular", headers=admin, json={"motivo": "No estaba en casa"}
    )
    assert r.status_code == 200, r.text
    (d,) = cliente.get(f"{API}/domicilios", headers=admin).json()
    assert d["estado"] == "cancelado"
    assert liquidacion(cliente, admin)["pendiente"] == 0
    assert esperado(cliente, admin)["Efectivo"] == 100000
    assert cerrar_cuadrada(cliente, admin)["Efectivo"] == 100000


def test_domiciliario_con_nombre_repetido(cliente, admin, domiciliario):
    r = cliente.post(f"{API}/domiciliarios", headers=admin, json={"nombre": "Carlos"})
    assert (r.status_code, r.json()["codigo"]) == (409, "NOMBRE_DUPLICADO")


def test_solo_quien_cierra_caja_liquida(
    cliente, admin, carta, metodos, domiciliario, crear_usuario, login
):
    vender(cliente, admin, a_domicilio(carta, metodos, domiciliario))
    cocina = login(crear_usuario("produccion"))
    assert liquidar(cliente, cocina, domiciliario).status_code == 403
