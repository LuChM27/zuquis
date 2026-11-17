"""Dashboard de Inicio (#45): cifras del día que coinciden con el reporte de ventas."""

from datetime import date

from tests.fixtures_encargos import abonar, crear_encargo, torta
from tests.fixtures_reportes import cortesia, malteada, reporte, seccion, vendida
from tests.fixtures_ventas import API, post, venta_mockup

HOY = date(2026, 11, 10)


def _dashboard(cliente, headers):
    r = cliente.get(f"{API}/reportes/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _dia(cliente, admin, carta, metodos, reloj):
    """Mockup ($46.500, costo $10.650) + malteada por Nequi ($16.000, costo $4.200) + cortesía
    (costo $4.200) + un gasto de caja de $5.000."""
    reloj("2026-11-10T09:00:00-05:00")
    r = cliente.post(f"{API}/caja/abrir", headers=admin, json={"base_inicial": 100000})
    assert r.status_code == 201, r.text
    reloj("2026-11-10T15:10:00-05:00")
    vendida(cliente, admin, venta_mockup(carta, metodos))
    reloj("2026-11-10T18:20:00-05:00")
    vendida(cliente, admin, malteada(carta, metodos, pago=16000, metodo="Nequi"))
    vendida(cliente, admin, cortesia(carta, metodos))
    cats = cliente.get(f"{API}/categorias-gasto", headers=admin).json()
    post(
        cliente,
        admin,
        "/gastos",
        {
            "fecha": str(HOY),
            "categoria_id": cats[0]["id"],
            "descripcion": "Bolsas",
            "monto": 5000,
            "metodo_pago_id": metodos["Efectivo"],
            "fuente": "caja",
        },
    )


def test_dashboard_igual_al_reporte_del_dia(cliente, admin, carta, metodos, reloj):
    _dia(cliente, admin, carta, metodos, reloj)
    d = _dashboard(cliente, admin)
    r = reporte(cliente, admin, "ventas", HOY, HOY).json()
    resumen = {f["concepto"]: f["valor"] for f in seccion(r, "Resumen")["filas"]}
    assert d["ventas"] == resumen["Ventas (sin propinas ni domicilios)"] == 62500
    assert d["n_ventas"] == resumen["Número de ventas"] == 3
    metodos_reporte = {f["metodo"]: f["ventas"] for f in seccion(r, "Por método de pago")["filas"]}
    assert {f["etiqueta"]: f["ventas"] for f in d["por_metodo"]} == metodos_reporte


def test_ganancia_y_ticket(cliente, admin, carta, metodos, reloj):
    _dia(cliente, admin, carta, metodos, reloj)
    d = _dashboard(cliente, admin)
    # 62.500 − 14.850 (insumos) − 4.200 (cortesía) − 5.000 (gasto) = 38.450
    assert (d["gastos"], d["n_gastos"], d["ganancia"]) == (5000, 1, 38450)
    # 62.500 / 2 ventas cobradas (la cortesía no cuenta) = 31.250
    assert d["ticket_promedio"] == 31250
    assert [f["clave"] for f in d["por_hora"]] == ["15", "18"]
    assert d["porcentaje_metodo"]["Efectivo"] == "44.19"  # 28.500 / 64.500
    assert d["mas_vendidos"][0]["etiqueta"] == "Malteada de brownie"


def test_encargos_hoy_con_saldo(cliente, admin, cliente_a, metodos, reloj):
    reloj("2026-11-10T09:00:00-05:00")
    cliente.post(f"{API}/caja/abrir", headers=admin, json={"base_inicial": 100000})
    e = crear_encargo(
        cliente, admin, torta(cliente_a["id"], fecha_entrega="2026-11-10T17:00:00-05:00")
    ).json()
    assert abonar(cliente, admin, e, 40000, metodos["Efectivo"]).status_code == 201
    crear_encargo(cliente, admin, torta(cliente_a["id"], fecha_entrega="2026-11-11T17:00:00-05:00"))
    d = _dashboard(cliente, admin)
    assert [(x["numero"], x["cliente"], x["saldo"]) for x in d["encargos_hoy"]] == [
        (e["numero"], "Cliente A", 50000)
    ]


def test_sin_caja_ni_datos(cliente, admin):
    d = _dashboard(cliente, admin)
    assert (d["ventas"], d["ticket_promedio"], d["ganancia"], d["caja_abierta_desde"]) == (
        0,
        0,
        0,
        None,
    )
    assert d["porcentaje_metodo"] == {}


def test_datos_ejemplo_lee_la_configuracion(cliente, admin):
    assert _dashboard(cliente, admin)["datos_ejemplo"] is False
    r = cliente.patch(f"{API}/configuracion", headers=admin, json={"datos_ejemplo": True})
    assert r.status_code == 200, r.text
    assert _dashboard(cliente, admin)["datos_ejemplo"] is True


def test_cajero_no_ve_dashboard(cliente, crear_usuario, login):
    cajero = login(crear_usuario("cajero", email="caja@zuquis.co"))
    assert cliente.get(f"{API}/reportes/dashboard", headers=cajero).status_code == 403
