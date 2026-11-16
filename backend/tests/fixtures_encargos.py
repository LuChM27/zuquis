"""Ayudas compartidas de la Fase 3: clientes, domiciliarios, encargos y cierres de caja."""

import uuid

import pytest

from tests.fixtures_ventas import API, post


@pytest.fixture
def cliente_a(cliente, admin):
    return post(
        cliente,
        admin,
        "/clientes",
        {
            "nombre": "Cliente A",
            "telefono": "300 123 4567",
            "direccion": "Cra 10 # 5-20",
            "autoriza_datos": True,
        },
    )


@pytest.fixture
def domiciliario(cliente, admin):
    return post(cliente, admin, "/domiciliarios", {"nombre": "Carlos", "telefono": "3101112233"})


def con_clave(headers):
    return headers | {"Idempotency-Key": str(uuid.uuid4())}


def torta(cliente_id, **extra):
    """El encargo del mockup: torta de cumpleaños de $90.000 que recogen en el local."""
    return {
        "cliente_id": cliente_id,
        "descripcion": "Torta de cumpleaños 1 lb · vainilla con fresas",
        "fecha_entrega": "2026-10-16T17:00:00-05:00",
        "items": [{"descripcion": "Torta de cumpleaños 1 lb", "cantidad": "1", "precio": 90000}],
    } | extra


def crear_encargo(cliente, headers, datos):
    return cliente.post(f"{API}/encargos", headers=con_clave(headers), json=datos)


def estado(cliente, headers, encargo, nuevo):
    return cliente.post(
        f"{API}/encargos/{encargo['id']}/estado", headers=headers, json={"estado": nuevo}
    )


def alistar(cliente, headers, encargo):
    """pendiente → en producción → listo."""
    for e in ("en_produccion", "listo"):
        r = estado(cliente, headers, encargo, e)
        assert r.status_code == 200, r.text
    return r.json()


def abonar(cliente, headers, encargo, monto, metodo_id):
    return cliente.post(
        f"{API}/encargos/{encargo['id']}/abonos",
        headers=con_clave(headers),
        json={"monto": monto, "metodo_pago_id": metodo_id},
    )


def entregar(cliente, headers, encargo, pagos, **extra):
    return cliente.post(
        f"{API}/encargos/{encargo['id']}/entregar",
        headers=con_clave(headers),
        json={"pagos": pagos} | extra,
    )


def cancelar(cliente, headers, encargo, datos=None):
    return cliente.post(
        f"{API}/encargos/{encargo['id']}/cancelar", headers=con_clave(headers), json=datos
    )


def cerrar_cuadrada(cliente, headers):
    """Cierra la caja contando exactamente lo esperado. Devuelve lo esperado por método (los
    que tienen dinero)."""
    vista = cliente.get(f"{API}/caja/actual/cierre", headers=headers).json()
    r = cliente.post(
        f"{API}/caja/cerrar",
        headers=headers,
        json={
            "contado": [
                {"metodo_pago_id": a["metodo_pago_id"], "contado": a["esperado"]}
                for a in vista["arqueo"]
            ]
        },
    )
    assert r.status_code == 200, r.text
    return {a["metodo"]: a["esperado"] for a in vista["arqueo"] if a["esperado"]}


def abrir_caja(cliente, headers, base=100000):
    r = cliente.post(f"{API}/caja/abrir", headers=headers, json={"base_inicial": base})
    assert r.status_code == 201, r.text
