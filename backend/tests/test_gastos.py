"""Gastos y categorías de gasto con PUC (#34, RF-21, RF-22, RF-23)."""

import pytest

from tests.fixtures_ventas import API, esperado


@pytest.fixture
def categorias(cliente, admin) -> dict[str, dict]:
    r = cliente.get(f"{API}/categorias-gasto", headers=admin)
    assert r.status_code == 200, r.text
    return {c["nombre"]: c for c in r.json()}


def gasto(cliente, headers, categoria, metodo, monto=46000, fuente="caja", **extra):
    return cliente.post(
        f"{API}/gastos",
        headers=headers,
        json={
            "categoria_id": categoria["id"],
            "descripcion": "Recibo de energía",
            "monto": monto,
            "metodo_pago_id": metodo,
            "fuente": fuente,
        }
        | extra,
    )


def test_categorias_iniciales_con_su_cuenta_puc(categorias):
    assert categorias["Arriendo del local"]["cuenta_puc"] == "5120"
    assert categorias["Servicios públicos (agua, energía, gas)"]["cuenta_puc"] == "5135"
    assert len(categorias) >= 13


def test_crear_y_editar_categoria(cliente, admin):
    r = cliente.post(
        f"{API}/categorias-gasto",
        headers=admin,
        json={"nombre": "Domicilios propios", "cuenta_puc": "5135"},
    )
    assert r.status_code == 201, r.text
    r = cliente.patch(
        f"{API}/categorias-gasto/{r.json()['id']}", headers=admin, json={"activa": False}
    )
    assert r.json()["activa"] is False


def test_gasto_de_caja_sale_del_arqueo(cliente, admin, categorias, metodos, caja_abierta):
    r = gasto(
        cliente, admin, categorias["Servicios públicos (agua, energía, gas)"], metodos["Efectivo"]
    )
    assert r.status_code == 201, r.text
    assert r.json()["caja_sesion_id"] is not None
    assert esperado(cliente, admin)["Efectivo"] == 100000 - 46000


def test_gasto_de_banco_no_afecta_el_arqueo(cliente, admin, categorias, metodos, caja_abierta):
    r = gasto(
        cliente, admin, categorias["Arriendo del local"], metodos["Nequi"], 1200000, fuente="banco"
    )
    assert r.status_code == 201, r.text
    assert r.json()["caja_sesion_id"] is None
    assert esperado(cliente, admin) == {**{n: 0 for n in metodos}, "Efectivo": 100000}


def test_gasto_de_caja_sin_caja_abierta(cliente, admin, categorias, metodos):
    r = gasto(cliente, admin, categorias["Papelería"], metodos["Efectivo"], 8000)
    assert (r.status_code, r.json()["codigo"]) == (409, "CAJA_CERRADA")


def test_gasto_de_los_duenos_no_necesita_caja(cliente, admin, categorias, metodos):
    r = gasto(cliente, admin, categorias["Publicidad"], metodos["Nequi"], 50000, fuente="duenos")
    assert r.status_code == 201, r.text


def test_cajero_solo_registra_gastos_de_caja(cliente, categorias, metodos, crear_usuario, login):
    cajero = login(crear_usuario("cajero"))
    cliente.post(f"{API}/caja/abrir", headers=cajero, json={"base_inicial": 50000})
    assert (
        gasto(cliente, cajero, categorias["Papelería"], metodos["Efectivo"], 8000).status_code
        == 201
    )
    r = gasto(cliente, cajero, categorias["Papelería"], metodos["Nequi"], 8000, fuente="banco")
    assert r.status_code == 403


def test_anular_gasto_de_caja_devuelve_el_dinero(cliente, admin, categorias, metodos, caja_abierta):
    g = gasto(cliente, admin, categorias["Papelería"], metodos["Efectivo"], 8000).json()
    r = cliente.post(
        f"{API}/gastos/{g['id']}/anular", headers=admin, json={"motivo": "Se registró dos veces"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "anulado"
    assert esperado(cliente, admin)["Efectivo"] == 100000


def test_listar_gastos_por_fuente(cliente, admin, categorias, metodos, caja_abierta):
    gasto(cliente, admin, categorias["Papelería"], metodos["Efectivo"], 8000)
    gasto(
        cliente, admin, categorias["Arriendo del local"], metodos["Nequi"], 900000, fuente="banco"
    )
    r = cliente.get(f"{API}/gastos", headers=admin, params={"fuente": "caja"})
    assert [g["monto"] for g in r.json()["items"]] == [8000]
    assert r.json()["items"][0]["categoria"] == "Papelería"
