"""Caso de control de la Fase 3 (#44): un encargo con dos abonos en días distintos y entrega con
saldo, otro cancelado con devolución parcial y tres domicilios de dos domiciliarios liquidados
al cierre. Los valores vienen de tests/control/fase3.md, calculados a mano.
"""

from decimal import Decimal as D

from tests.fixtures_encargos import (
    abonar,
    abrir_caja,
    alistar,
    cancelar,
    cerrar_cuadrada,
    crear_encargo,
    entregar,
)
from tests.fixtures_ventas import API, post, stock, vender


def _a_domicilio(producto, cantidad, total, valor, domiciliario, metodo_id):
    return {
        "tipo_servicio": "domicilio",
        "items": [{"producto_id": producto["id"], "cantidad": cantidad}],
        "valor_domicilio": valor,
        "domicilio": {"domiciliario_id": domiciliario["id"], "direccion": "Calle 20 # 8-15"},
        "pagos": [{"metodo_pago_id": metodo_id, "monto": total + valor}],
    }


def _liquidar(cliente, admin, domiciliario, monto):
    r = cliente.post(
        f"{API}/caja/liquidar-domicilios",
        headers=admin,
        json={"domiciliario_id": domiciliario["id"], "monto": monto},
    )
    assert r.status_code == 200, r.text


def _caja(cliente, admin, sesion_id):
    return cliente.get(f"{API}/caja/sesiones/{sesion_id}", headers=admin).json()


def _ventas_de(cliente, admin, sesion_id):
    r = cliente.get(f"{API}/ventas", headers=admin, params={"caja_sesion_id": sesion_id})
    return sorted(r.json()["items"], key=lambda v: v["numero"])


def test_dos_dias_de_encargos_y_domicilios_cuadran_al_peso(cliente, admin, carta, metodos, db):
    efectivo, nequi = metodos["Efectivo"], metodos["Nequi"]
    cliente_a = post(cliente, admin, "/clientes", {"nombre": "Cliente A", "telefono": "3001112233"})
    cliente_b = post(cliente, admin, "/clientes", {"nombre": "Cliente B", "telefono": "3004445566"})
    carlos = post(cliente, admin, "/domiciliarios", {"nombre": "Carlos"})
    diana = post(cliente, admin, "/domiciliarios", {"nombre": "Diana"})

    # ------------------------------------------------------------------ Día 1
    abrir_caja(cliente, admin)
    caja_1 = cliente.get(f"{API}/caja/actual", headers=admin).json()["sesion"]["id"]

    e1 = crear_encargo(
        cliente,
        admin,
        {
            "cliente_id": cliente_a["id"],
            "fecha_entrega": "2026-10-17T17:00:00-05:00",
            "tipo_entrega": "domicilio",
            "direccion_entrega": "Cra 9 # 14-30",
            "items": [
                {"descripcion": "Torta de cumpleaños 1 lb", "cantidad": "1", "precio": 90000}
            ],
            "abono": {"monto": 30000, "metodo_pago_id": nequi},
        },
    ).json()
    e2 = crear_encargo(
        cliente,
        admin,
        {
            "cliente_id": cliente_b["id"],
            "fecha_entrega": "2026-10-18T15:00:00-05:00",
            "items": [{"descripcion": "Cupcakes decorados", "cantidad": "24", "precio": 2500}],
            "abono": {"monto": 40000, "metodo_pago_id": efectivo},
        },
    ).json()
    assert (e1["total"], e1["saldo"], e2["total"], e2["saldo"]) == (90000, 60000, 60000, 20000)

    v1 = vender(cliente, admin, _a_domicilio(carta["pastel"], "2", 9000, 4000, carlos, efectivo))
    assert v1.status_code == 201, v1.text
    _liquidar(cliente, admin, carlos, 4000)

    assert cerrar_cuadrada(cliente, admin) == {"Efectivo": 149000, "Nequi": 30000}
    dia_1 = _caja(cliente, admin, caja_1)
    assert dia_1["resumen"] | {"gastos": 0} == {
        "ventas": 9000,
        "abonos": 70000,
        "propinas": 0,
        "gastos": 0,
        "domicilios_entregados": 4000,
        "pagos_proveedores": 0,
        "anulaciones": 0,
    }
    assert dia_1["diferencia_total"] == 0
    ventas_1 = _ventas_de(cliente, admin, caja_1)
    assert [(v["total"], v["costo_total"]) for v in ventas_1] == [(9000, 1350)]

    # ------------------------------------------------------------------ Día 2
    abrir_caja(cliente, admin)
    caja_2 = cliente.get(f"{API}/caja/actual", headers=admin).json()["sesion"]["id"]

    assert abonar(cliente, admin, e1, 20000, efectivo).json()["saldo"] == 40000

    cancelado = cancelar(
        cliente,
        admin,
        e2,
        {
            "decision": "devuelve_parcial",
            "monto_devuelto": 25000,
            "motivo": "Canceló con la producción ya empezada",
        },
    ).json()
    assert (cancelado["monto_devuelto"], cancelado["monto_retenido"]) == (25000, 15000)

    v2 = vender(cliente, admin, _a_domicilio(carta["croissant"], "1", 7500, 5000, diana, nequi))
    assert v2.status_code == 201, v2.text

    alistar(cliente, admin, e1)
    entregado = entregar(
        cliente,
        admin,
        e1,
        [{"metodo_pago_id": efectivo, "monto": 46000}],
        valor_domicilio=6000,
        domicilio={"domiciliario_id": carlos["id"], "direccion": "Cra 9 # 14-30"},
    )
    assert entregado.status_code == 200, entregado.text
    assert (entregado.json()["estado"], entregado.json()["saldo"]) == ("entregado", 0)

    turno = cliente.get(f"{API}/caja/actual/domicilios", headers=admin).json()
    assert {d["domiciliario"]: d["pendiente"] for d in turno["domiciliarios"]} == {
        "Carlos": 6000,
        "Diana": 5000,
    }
    _liquidar(cliente, admin, carlos, 6000)
    _liquidar(cliente, admin, diana, 5000)

    assert cerrar_cuadrada(cliente, admin) == {"Efectivo": 130000, "Nequi": 12500}
    dia_2 = _caja(cliente, admin, caja_2)
    assert dia_2["resumen"] == {
        "ventas": 7500,
        "abonos": 60000,
        "propinas": 0,
        "gastos": 0,
        "domicilios_entregados": 11000,
        "pagos_proveedores": 0,
        "anulaciones": 0,
    }
    assert {x["concepto"]: x["monto"] for x in dia_2["efectivo"]} == {
        "Base inicial": 100000,
        "Abonos de encargos": 20000,
        "Saldos de encargos": 40000,
        "Domicilios cobrados": 6000,
        "Devoluciones de abonos": -25000,
        "Entregado al domiciliario": -11000,
    }

    # Ventas del día de entrega (RN-20): el encargo completo cuenta hoy.
    ventas_2 = _ventas_de(cliente, admin, caja_2)
    assert [
        (v["total"], v["abonos_aplicados"], v["valor_domicilio"], v["cobrado"], v["costo_total"])
        for v in ventas_2
    ] == [(7500, 0, 5000, 12500, 2000), (90000, 50000, 6000, 46000, 0)]
    assert sum(v["total"] for v in ventas_2) == 97500

    # ------------------------------------------------------------- Cruces finales
    resumen = cliente.get(f"{API}/ventas/resumen", headers=admin).json()
    assert (resumen["total"], resumen["domicilios"], resumen["ingresos_cancelacion"]) == (
        106500,
        15000,
        15000,
    )
    neto = (149000 - 100000) + 30000 + (130000 - 100000) + 12500
    assert neto == 121500 == resumen["total"] + resumen["ingresos_cancelacion"]

    domicilios = cliente.get(f"{API}/domicilios", headers=admin).json()
    assert sorted((d["domiciliario"], d["valor"]) for d in domicilios) == [
        ("Carlos", 4000),
        ("Carlos", 6000),
        ("Diana", 5000),
    ]
    assert all(d["liquidado_en"] for d in domicilios)
    assert stock(db, "producto", carta["pastel"]["id"]) == D("10")
    assert stock(db, "producto", carta["croissant"]["id"]) == D("7")
