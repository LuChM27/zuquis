"""Proveedores y compras con lotes y cuentas por pagar (#19)."""

import uuid
from decimal import Decimal as D

import pytest
from sqlalchemy import func, select

from app.core.deps import Contexto
from app.modules.compras.models import Compra
from app.modules.inventario import motor
from app.modules.inventario.models import Lote
from tests.conftest import SEDE_PRINCIPAL

API = "/api/v1"


@pytest.fixture
def harina(cliente, admin):
    r = cliente.post(
        f"{API}/insumos",
        headers=admin,
        json={
            "nombre": "Harina compras",
            "unidad_base": "g",
            "presentaciones": [{"nombre": "Bulto 50 kg", "factor": "50000"}],
        },
    )
    return r.json()


@pytest.fixture
def efectivo(cliente, admin):
    return next(
        m["id"]
        for m in cliente.get(f"{API}/metodos-pago", headers=admin).json()
        if m["es_efectivo"]
    )


@pytest.fixture
def proveedor(cliente, admin, harina):
    return cliente.post(
        f"{API}/proveedores",
        headers=admin,
        json={"nombre": "Proveedor A", "insumo_ids": [harina["id"]]},
    ).json()


def comprar(
    cliente,
    headers,
    harina,
    *,
    estado="por_pagar",
    metodo=None,
    proveedor=None,
    bultos="1",
    costo=150000,
    key=None,
):
    datos = {
        "estado_pago": estado,
        "proveedor_id": proveedor["id"] if proveedor else None,
        "metodo_pago_id": metodo,
        "items": [
            {
                "insumo_id": harina["id"],
                "presentacion_id": harina["presentaciones"][0]["id"],
                "cantidad": bultos,
                "costo_total": costo,
            }
        ],
    }
    extra = {"Idempotency-Key": key} if key else {}
    return cliente.post(f"{API}/compras", headers=headers | extra, json=datos)


def test_un_bulto_de_50_kg_crea_un_lote_de_50000_g_a_3_pesos(cliente, admin, harina, db):
    r = comprar(cliente, admin, harina)
    assert r.status_code == 201, r.json()
    item = r.json()["items"][0]
    assert (item["cantidad_base"], item["costo_unitario"]) == ("50000.0000", "3.000000")
    lote = db.get(Lote, uuid.UUID(item["lote_id"]))
    assert (lote.cantidad_inicial, lote.costo_unitario, lote.origen) == (
        D("50000"),
        D("3"),
        "compra",
    )


def test_proveedor_con_los_insumos_que_suministra(proveedor, harina):
    assert [i["nombre"] for i in proveedor["insumos"]] == [harina["nombre"]]


def test_de_contado_registra_el_pago_inmediato(cliente, admin, harina, efectivo):
    r = comprar(cliente, admin, harina, estado="contado", metodo=efectivo)
    compra = r.json()
    assert (compra["estado_pago"], compra["pagado"], compra["saldo"]) == ("contado", 150000, 0)
    assert compra["pagos"][0]["metodo_pago"] == "Efectivo"
    # De contado sin método de pago es un error de validación.
    assert comprar(cliente, admin, harina, estado="contado").status_code == 422


def test_pagos_no_superan_el_total_y_al_completar_queda_pagada(cliente, admin, harina, efectivo):
    compra = comprar(cliente, admin, harina).json()
    url = f"{API}/compras/{compra['id']}/pagos"
    r = cliente.post(url, headers=admin, json={"monto": 100000, "metodo_pago_id": efectivo})
    assert (r.json()["estado_pago"], r.json()["saldo"]) == ("por_pagar", 50000)
    r = cliente.post(url, headers=admin, json={"monto": 50001, "metodo_pago_id": efectivo})
    assert (r.status_code, r.json()["codigo"], r.json()["detalle"]) == (
        422,
        "PAGO_EXCEDE_SALDO",
        {"saldo": 50000},
    )
    r = cliente.post(url, headers=admin, json={"monto": 50000, "metodo_pago_id": efectivo})
    assert (r.json()["estado_pago"], r.json()["saldo"]) == ("pagada", 0)
    r = cliente.post(url, headers=admin, json={"monto": 1, "metodo_pago_id": efectivo})
    assert r.json()["codigo"] == "COMPRA_PAGADA"


def test_cuentas_por_pagar_por_proveedor(cliente, admin, harina, proveedor, efectivo):
    comprar(cliente, admin, harina, proveedor=proveedor, costo=150000)
    segunda = comprar(cliente, admin, harina, proveedor=proveedor, costo=100000).json()
    comprar(
        cliente, admin, harina, estado="contado", metodo=efectivo, proveedor=proveedor
    )  # no se debe
    cliente.post(
        f"{API}/compras/{segunda['id']}/pagos",
        headers=admin,
        json={"monto": 40000, "metodo_pago_id": efectivo},
    )
    cuentas = cliente.get(f"{API}/compras/por-pagar", headers=admin).json()
    cuenta = next(c for c in cuentas if c["proveedor_id"] == proveedor["id"])
    assert (cuenta["compras"], cuenta["saldo"]) == (2, 210000)


def test_anular_compra_sin_consumos_retira_el_lote(cliente, admin, harina, db):
    compra = comprar(cliente, admin, harina).json()
    r = cliente.post(
        f"{API}/compras/{compra['id']}/anular", headers=admin, json={"motivo": "Factura duplicada"}
    )
    assert r.status_code == 200, r.json()
    assert r.json()["anulada"] is True
    lote = db.get(Lote, uuid.UUID(compra["items"][0]["lote_id"]))
    db.refresh(lote)
    assert lote.cantidad_disponible == 0
    r = cliente.post(
        f"{API}/compras/{compra['id']}/anular", headers=admin, json={"motivo": "otra vez"}
    )
    assert r.json()["codigo"] == "YA_ANULADO"


def test_anular_compra_con_consumos_da_error_claro(cliente, admin, harina, db, crear_usuario):
    compra = comprar(cliente, admin, harina).json()
    ctx = Contexto(usuario_id=crear_usuario("admin").id, sede_id=SEDE_PRINCIPAL)
    motor.consumir(
        db,
        ctx,
        tipo_item="insumo",
        item_id=uuid.UUID(harina["id"]),
        cantidad=D("100"),
        tipo_mov="consumo_produccion",
        referencia_tipo="prueba",
        referencia_id=uuid.uuid4(),
    )
    db.commit()
    r = cliente.post(
        f"{API}/compras/{compra['id']}/anular", headers=admin, json={"motivo": "Error"}
    )
    assert (r.status_code, r.json()["codigo"]) == (409, "COMPRA_CON_CONSUMOS")


def test_reintento_con_la_misma_clave_no_duplica_la_compra(cliente, admin, harina, db):
    clave = f"compra-{uuid.uuid4()}"
    r1 = comprar(cliente, admin, harina, key=clave)
    r2 = comprar(cliente, admin, harina, key=clave)
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.headers.get("Idempotent-Replayed") == "true"
    assert (
        db.scalar(
            select(func.count()).select_from(Compra).where(Compra.id == uuid.UUID(r1.json()["id"]))
        )
        == 1
    )


def test_una_linea_invalida_no_deja_nada_registrado(cliente, admin, harina, db):
    antes = db.scalar(select(func.count()).select_from(Lote))
    datos = {
        "estado_pago": "por_pagar",
        "items": [
            {"insumo_id": harina["id"], "cantidad": "1000", "costo_total": 3000},
            {"insumo_id": str(uuid.uuid4()), "cantidad": "1", "costo_total": 1},
        ],
    }
    assert cliente.post(f"{API}/compras", headers=admin, json=datos).status_code == 404
    assert db.scalar(select(func.count()).select_from(Lote)) == antes


def test_permisos_de_compras(cliente, admin, harina, crear_usuario, login):
    cajero = login(crear_usuario("cajero"))
    produccion = login(crear_usuario("produccion"))
    assert comprar(cliente, cajero, harina).status_code == 403
    compra = comprar(cliente, produccion, harina).json()
    # Producción registra compras pero no las anula (compras.anular es del admin).
    r = cliente.post(
        f"{API}/compras/{compra['id']}/anular", headers=produccion, json={"motivo": "x" * 5}
    )
    assert r.status_code == 403
