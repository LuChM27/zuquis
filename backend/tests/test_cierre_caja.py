"""Cierre de caja con arqueo, desglose del efectivo e historial (#32, RF-19, RF-20, RN-13)."""

import uuid

import pytest

from app.core.deps import Contexto
from app.modules.caja import service as caja
from tests.conftest import SEDE_PRINCIPAL
from tests.fixtures_ventas import API

pytestmark = pytest.mark.usefixtures("caja_abierta")


@pytest.fixture
def mov(db, crear_usuario, metodos):
    """Registra un movimiento como lo harán ventas, abonos, gastos y domicilios."""
    ctx = Contexto(usuario_id=crear_usuario("admin").id, sede_id=SEDE_PRINCIPAL)

    def registrar(tipo, metodo, monto):
        caja.registrar_movimiento(
            db,
            ctx,
            tipo=tipo,
            metodo_pago_id=uuid.UUID(metodos[metodo]),
            monto=monto,
            referencia_tipo="prueba",
            referencia_id=uuid.uuid4(),
        )
        db.commit()

    return registrar


@pytest.fixture
def turno_del_mockup(mov, cliente, admin, metodos):
    """El turno del mockup "Cierre de caja" (caja con base de $100.000)."""
    for metodo in ("Bre-B", "Bancolombia"):
        if metodo not in metodos:
            r = cliente.post(
                f"{API}/metodos-pago", headers=admin, json={"nombre": metodo, "titular": "negocio"}
            )
            assert r.status_code == 201, r.text
            metodos[metodo] = r.json()["id"]
    mov("venta", "Efectivo", 280600)
    mov("propina", "Efectivo", 6000)
    mov("abono", "Efectivo", 50000)
    mov("domicilio", "Efectivo", 16000)
    mov("gasto", "Efectivo", -46000)
    mov("pago_domiciliario", "Efectivo", -16000)
    mov("venta", "Nequi", 225900)
    mov("abono", "Nequi", 40000)
    mov("venta", "Bre-B", 123200)
    mov("venta", "Bancolombia", 54800)
    return metodos


def cierre(cliente, headers):
    r = cliente.get(f"{API}/caja/actual/cierre", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def cerrar(cliente, headers, contado: dict[str, int], metodos, observacion=None):
    return cliente.post(
        f"{API}/caja/cerrar",
        headers=headers,
        json={
            "contado": [{"metodo_pago_id": metodos[n], "contado": v} for n, v in contado.items()],
            "observacion": observacion,
        },
    )


CONTADO_MOCKUP = {"Efectivo": 390000, "Nequi": 265900, "Bre-B": 123200, "Bancolombia": 54800}


def test_vista_previa_reproduce_el_mockup_al_peso(cliente, admin, turno_del_mockup):
    c = cierre(cliente, admin)
    esperado = {a["metodo"]: a["esperado"] for a in c["arqueo"]}
    assert {k: esperado[k] for k in CONTADO_MOCKUP} == {
        "Efectivo": 390600,
        "Nequi": 265900,
        "Bre-B": 123200,
        "Bancolombia": 54800,
    }
    assert [(d["concepto"], d["monto"]) for d in c["efectivo"]] == [
        ("Base inicial", 100000),
        ("Ventas en efectivo", 280600),
        ("Propinas en efectivo", 6000),
        ("Abonos de encargos", 50000),
        ("Domicilios cobrados", 16000),
        ("Gastos pagados de la caja", -46000),
        ("Entregado al domiciliario", -16000),
    ]
    assert c["efectivo_esperado"] == 390600
    r = c["resumen"]
    assert (r["ventas"], r["abonos"], r["propinas"], r["gastos"], r["domicilios_entregados"]) == (
        684500,
        90000,
        6000,
        46000,
        16000,
    )


def test_cerrar_con_diferencia_exige_observacion(cliente, admin, turno_del_mockup):
    r = cerrar(cliente, admin, CONTADO_MOCKUP, turno_del_mockup)
    assert (r.status_code, r.json()["codigo"]) == (422, "OBSERVACION_REQUERIDA")
    assert cliente.get(f"{API}/caja/actual", headers=admin).json()["abierta"] is True


def test_cerrar_guarda_el_arqueo_tal_cual(cliente, admin, turno_del_mockup):
    r = cerrar(
        cliente,
        admin,
        CONTADO_MOCKUP,
        turno_del_mockup,
        "Faltan $600 en efectivo, posiblemente cambio mal entregado.",
    )
    assert r.status_code == 200, r.text
    sesion = r.json()
    arqueo = {
        a["metodo"]: (a["esperado"], a["contado"], a["diferencia"]) for a in sesion["arqueos"]
    }
    assert arqueo["Efectivo"] == (390600, 390000, -600)
    assert arqueo["Nequi"] == (265900, 265900, 0)
    assert sesion["estado"] == "cerrada" and sesion["observacion"].startswith("Faltan $600")
    assert cliente.get(f"{API}/caja/actual", headers=admin).json()["abierta"] is False


def test_sin_diferencias_no_pide_observacion(cliente, admin, metodos, mov):
    mov("venta", "Efectivo", 10000)
    r = cerrar(cliente, admin, {"Efectivo": 110000, "Nequi": 0}, metodos)
    assert r.status_code == 200, r.text


def test_cada_metodo_con_esperado_debe_contarse(cliente, admin, metodos, mov):
    mov("venta", "Nequi", 10000)
    r = cerrar(cliente, admin, {"Efectivo": 100000}, metodos)
    assert (r.status_code, r.json()["codigo"]) == (422, "FALTA_CONTAR")
    assert "Nequi" in r.json()["mensaje"]


def test_caja_cerrada_no_admite_movimientos(cliente, admin, metodos):
    cerrar(cliente, admin, {"Efectivo": 100000}, metodos)
    r = cliente.post(
        f"{API}/caja/movimientos",
        headers=admin,
        json={
            "tipo": "entrada_manual",
            "metodo_pago_id": metodos["Efectivo"],
            "monto": 1000,
            "motivo": "Prueba",
        },
    )
    assert (r.status_code, r.json()["codigo"]) == (409, "CAJA_CERRADA")


def test_historial_de_cierres(cliente, admin, metodos, turno_del_mockup):
    cerrar(cliente, admin, CONTADO_MOCKUP, turno_del_mockup, "Faltan $600.")
    r = cliente.get(f"{API}/caja/sesiones", headers=admin)
    assert r.status_code == 200, r.text
    (sesion,) = r.json()["items"]
    assert (sesion["estado"], sesion["diferencia_total"], sesion["efectivo_esperado"]) == (
        "cerrada",
        -600,
        390600,
    )
    detalle = cliente.get(f"{API}/caja/sesiones/{sesion['id']}", headers=admin).json()
    assert detalle["resumen"]["ventas"] == 684500
    assert len(detalle["arqueos"]) >= 4


def test_el_cajero_no_ve_el_historial_de_otros(cliente, admin, metodos, crear_usuario, login):
    cerrar(cliente, admin, {"Efectivo": 100000}, metodos)
    contador = login(crear_usuario("contador"))
    assert cliente.get(f"{API}/caja/sesiones", headers=contador).status_code == 200
    cajero = login(crear_usuario("cajero"))
    # El cajero solo ve sus propias cajas.
    assert cliente.get(f"{API}/caja/sesiones", headers=cajero).json()["total"] == 0
