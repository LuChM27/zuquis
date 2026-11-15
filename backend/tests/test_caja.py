"""Caja: apertura, movimientos manuales, estado actual y pagos de compra desde caja (#28)."""

import uuid

import pytest
from sqlalchemy import text

from app.core.deps import Contexto
from app.modules.caja import service as caja
from tests.conftest import SEDE_PRINCIPAL

API = "/api/v1"


@pytest.fixture
def metodos(cliente, admin) -> dict[str, str]:
    return {m["nombre"]: m["id"] for m in cliente.get(f"{API}/metodos-pago", headers=admin).json()}


def abrir(cliente, headers, base=100000):
    return cliente.post(f"{API}/caja/abrir", headers=headers, json={"base_inicial": base})


def movimiento(cliente, headers, tipo, metodo, monto, motivo="Cambio para la caja"):
    return cliente.post(
        f"{API}/caja/movimientos",
        headers=headers,
        json={"tipo": tipo, "metodo_pago_id": metodo, "monto": monto, "motivo": motivo},
    )


def esperado(cliente, headers) -> dict[str, int]:
    actual = cliente.get(f"{API}/caja/actual", headers=headers).json()
    return {e["metodo"]: e["esperado"] for e in actual["esperado"]}


def test_sin_caja_abierta_el_estado_lo_dice(cliente, admin):
    r = cliente.get(f"{API}/caja/actual", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["abierta"] is False


def test_abrir_caja_con_base(cliente, admin):
    r = abrir(cliente, admin)
    assert r.status_code == 201, r.text
    actual = cliente.get(f"{API}/caja/actual", headers=admin).json()
    assert actual["abierta"] is True
    assert actual["sesion"]["base_inicial"] == 100000
    assert actual["sesion"]["responsable"]


def test_no_se_abren_dos_cajas_en_la_sede(cliente, admin):
    abrir(cliente, admin)
    r = abrir(cliente, admin)
    assert (r.status_code, r.json()["codigo"]) == (409, "CAJA_YA_ABIERTA")


def test_movimiento_sin_caja_abierta(cliente, admin, metodos):
    r = movimiento(cliente, admin, "entrada_manual", metodos["Efectivo"], 5000)
    assert (r.status_code, r.json()["codigo"]) == (409, "CAJA_CERRADA")


def test_esperado_por_metodo_es_base_mas_movimientos(cliente, admin, metodos):
    """RN-13: la base solo cuenta en efectivo; cada método suma sus movimientos."""
    abrir(cliente, admin, base=100000)
    movimiento(cliente, admin, "entrada_manual", metodos["Efectivo"], 20000)
    movimiento(cliente, admin, "salida_manual", metodos["Efectivo"], 15000, "Retiro de los dueños")
    movimiento(cliente, admin, "entrada_manual", metodos["Nequi"], 8000, "Transferencia de prueba")
    assert esperado(cliente, admin) | {} == {
        **{n: 0 for n in metodos},
        "Efectivo": 105000,
        "Nequi": 8000,
    }


def test_la_salida_se_guarda_negativa_con_su_motivo(cliente, admin, metodos):
    abrir(cliente, admin)
    r = movimiento(
        cliente, admin, "salida_manual", metodos["Efectivo"], 15000, "Retiro de los dueños"
    )
    assert r.status_code == 201, r.text
    assert (r.json()["monto"], r.json()["motivo"], r.json()["tipo"]) == (
        -15000,
        "Retiro de los dueños",
        "salida_manual",
    )


def test_movimiento_manual_exige_motivo_y_monto_positivo(cliente, admin, metodos):
    abrir(cliente, admin)
    assert movimiento(cliente, admin, "entrada_manual", metodos["Efectivo"], 0).status_code == 422
    assert (
        movimiento(cliente, admin, "entrada_manual", metodos["Efectivo"], 100, "").status_code
        == 422
    )
    # Los tipos automáticos (venta, gasto…) no se registran a mano.
    assert movimiento(cliente, admin, "venta", metodos["Efectivo"], 100).status_code == 422


def test_reintento_de_movimiento_no_lo_duplica(cliente, admin, metodos):
    abrir(cliente, admin)
    datos = {
        "tipo": "entrada_manual",
        "metodo_pago_id": metodos["Efectivo"],
        "monto": 5000,
        "motivo": "Cambio",
    }
    clave = {"Idempotency-Key": str(uuid.uuid4())}
    for _ in range(2):
        r = cliente.post(f"{API}/caja/movimientos", headers=admin | clave, json=datos)
        assert r.status_code == 201
    assert esperado(cliente, admin)["Efectivo"] == 105000


def test_el_libro_de_caja_no_se_modifica(cliente, admin, metodos, db):
    abrir(cliente, admin)
    movimiento(cliente, admin, "entrada_manual", metodos["Efectivo"], 5000)
    with pytest.raises(Exception, match="solo admite inserciones|no se puede"):
        db.execute(text("UPDATE caja_movimientos SET monto = 1"))
    db.rollback()


def test_servicio_de_movimientos_usa_la_caja_abierta(cliente, admin, metodos, db, crear_usuario):
    abrir(cliente, admin)
    ctx = Contexto(usuario_id=crear_usuario("admin").id, sede_id=SEDE_PRINCIPAL)
    caja.registrar_movimiento(
        db,
        ctx,
        tipo="venta",
        metodo_pago_id=uuid.UUID(metodos["Nequi"]),
        monto=12500,
        referencia_tipo="venta",
        referencia_id=uuid.uuid4(),
    )
    db.commit()
    assert esperado(cliente, admin)["Nequi"] == 12500


def test_cajero_puede_abrir_y_ver_pero_contador_no(cliente, crear_usuario, login, metodos):
    cajero = login(crear_usuario("cajero"))
    assert abrir(cliente, cajero).status_code == 201
    assert cliente.get(f"{API}/caja/actual", headers=cajero).status_code == 200
    contador = login(crear_usuario("contador"))
    assert abrir(cliente, contador).status_code == 403


# --- Pagos de compra desde caja ------------------------------------------------------------


@pytest.fixture
def harina(cliente, admin):
    return cliente.post(
        f"{API}/insumos", headers=admin, json={"nombre": "Harina caja", "unidad_base": "g"}
    ).json()


def compra(cliente, headers, harina, **datos):
    return cliente.post(
        f"{API}/compras",
        headers=headers,
        json={"items": [{"insumo_id": harina["id"], "cantidad": "1000", "costo_total": 30000}]}
        | datos,
    )


def test_compra_de_contado_desde_caja_sale_del_efectivo(cliente, admin, metodos, harina):
    abrir(cliente, admin, base=100000)
    r = compra(
        cliente,
        admin,
        harina,
        estado_pago="contado",
        metodo_pago_id=metodos["Efectivo"],
        desde_caja=True,
    )
    assert r.status_code == 201, r.text
    assert esperado(cliente, admin)["Efectivo"] == 70000


def test_compra_de_contado_desde_caja_sin_caja_abierta(cliente, admin, metodos, harina):
    r = compra(
        cliente,
        admin,
        harina,
        estado_pago="contado",
        metodo_pago_id=metodos["Efectivo"],
        desde_caja=True,
    )
    assert (r.status_code, r.json()["codigo"]) == (409, "CAJA_CERRADA")


def test_compra_pagada_por_banco_no_toca_la_caja(cliente, admin, metodos, harina):
    abrir(cliente, admin, base=100000)
    r = compra(cliente, admin, harina, estado_pago="contado", metodo_pago_id=metodos["Nequi"])
    assert r.status_code == 201, r.text
    assert esperado(cliente, admin) == {**{n: 0 for n in metodos}, "Efectivo": 100000}


def test_abono_a_proveedor_desde_caja(cliente, admin, metodos, harina):
    abrir(cliente, admin, base=100000)
    c = compra(cliente, admin, harina, estado_pago="por_pagar").json()
    r = cliente.post(
        f"{API}/compras/{c['id']}/pagos",
        headers=admin,
        json={"monto": 10000, "metodo_pago_id": metodos["Efectivo"], "desde_caja": True},
    )
    assert r.status_code == 200, r.text
    assert esperado(cliente, admin)["Efectivo"] == 90000


def test_anular_compra_pagada_desde_caja_devuelve_el_dinero(cliente, admin, metodos, harina):
    abrir(cliente, admin, base=100000)
    c = compra(
        cliente,
        admin,
        harina,
        estado_pago="contado",
        metodo_pago_id=metodos["Efectivo"],
        desde_caja=True,
    ).json()
    r = cliente.post(
        f"{API}/compras/{c['id']}/anular", headers=admin, json={"motivo": "Error de digitación"}
    )
    assert r.status_code == 200, r.text
    assert esperado(cliente, admin)["Efectivo"] == 100000
