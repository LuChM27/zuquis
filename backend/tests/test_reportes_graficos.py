"""Datos de la galería de gráficos (fase 4). Valores calculados a mano."""

from datetime import date

from tests.fixtures_encargos import abonar, cancelar, crear_encargo, torta
from tests.fixtures_reportes import cortesia, malteada, reporte, seccion, vendida
from tests.fixtures_ventas import API, post, venta_mockup

HOY = date(2026, 11, 10)
GRUPOS = ("ganancia", "ventas", "productos", "gastos", "encargos", "cajeros")


def _grupo(cliente, headers, grupo, desde=HOY, hasta=HOY):
    return cliente.get(
        f"{API}/reportes/graficos",
        headers=headers,
        params={"grupo": grupo, "desde": str(desde), "hasta": str(hasta)},
    )


def _abrir(cliente, admin, reloj, momento="2026-11-10T09:00:00-05:00"):
    reloj(momento)
    r = cliente.post(f"{API}/caja/abrir", headers=admin, json={"base_inicial": 100000})
    assert r.status_code == 201, r.text


def test_cascada_cuadra_con_reportes(cliente, admin, carta, metodos, reloj):
    _abrir(cliente, admin, reloj)
    vendida(cliente, admin, venta_mockup(carta, metodos))
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
    r = _grupo(cliente, admin, "ganancia")
    assert r.status_code == 200, r.text
    cascada = r.json()["cascada"]
    ventas = reporte(cliente, admin, "ventas", HOY, HOY).json()
    gastos = reporte(cliente, admin, "gastos", HOY, HOY).json()
    assert cascada["ventas"] == seccion(ventas, "Por día")["totales"]["ventas"] == 62500
    assert cascada["gastos"] == seccion(gastos, "Por categoría")["totales"]["monto"] == 5000
    # 62.500 − 14.850 − 4.200 (regalado) − 5.000 = 38.450
    assert (cascada["costo_insumos"], cascada["regalado"], cascada["utilidad"]) == (
        14850,
        4200,
        38450,
    )
    assert r.json()["costo_pct"] == [
        {"semana": "2026-W46", "ventas": 62500, "costo": 14850, "pct": "23.76"}
    ]


def test_calor_en_hora_local(cliente, admin, carta, metodos, reloj):
    _abrir(cliente, admin, reloj, "2026-11-10T23:00:00-05:00")
    reloj("2026-11-10T23:30:00-05:00")
    vendida(cliente, admin, malteada(carta, metodos, pago=16000))
    calor = _grupo(cliente, admin, "ventas").json()["calor"]
    assert calor == [{"dow": 2, "hora": 23, "ventas": 16000}]  # martes


def test_menos_vendidos_incluye_productos_sin_ventas(cliente, admin, carta, metodos, reloj):
    _abrir(cliente, admin, reloj)
    vendida(
        cliente,
        admin,
        {
            "tipo_servicio": "local",
            "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "1"}],
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 4500}],
        },
    )
    datos = _grupo(cliente, admin, "productos").json()
    menos = {f["producto"]: f["unidades"] for f in datos["menos_vendidos"]}
    assert menos["Soda frutos rojos"] == 0
    assert datos["menos_vendidos"][-1]["producto"] == "Pastel de pollo"
    assert datos["mas_vendidos"][0]["producto"] == "Pastel de pollo"


def test_por_pagar_con_y_sin_fecha(cliente, admin, reloj):
    reloj("2026-11-10T09:00:00-05:00")
    harina = post(cliente, admin, "/insumos", {"nombre": "Harina pp", "unidad_base": "g"})

    def comprar(fecha, costo, limite=None):
        post(
            cliente,
            admin,
            "/compras",
            {
                "estado_pago": "por_pagar",
                "fecha": fecha,
                "fecha_limite_pago": limite,
                "items": [{"insumo_id": harina["id"], "cantidad": "1", "costo_total": costo}],
            },
        )

    comprar("2026-11-01", 30000, "2026-11-05")  # vencida
    comprar("2026-11-08", 8000, "2026-11-14")  # esta semana
    comprar("2026-10-21", 12000)  # sin fecha, 20 días
    datos = _grupo(cliente, admin, "gastos").json()["por_pagar"]
    assert datos == {
        "con_fecha": {"vencidas": 30000, "esta_semana": 8000, "proximas": 0},
        "sin_fecha": {"d0_15": 0, "d16_30": 12000, "d30_mas": 0},
    }


def test_abonos_sin_entregar_a_la_fecha(cliente, admin, cliente_a, metodos, reloj):
    _abrir(cliente, admin, reloj)
    e = crear_encargo(cliente, admin, torta(cliente_a["id"])).json()
    assert abonar(cliente, admin, e, 40000, metodos["Efectivo"]).status_code == 201
    reloj("2026-11-12T10:00:00-05:00")
    datos = {"decision": "devuelve_total", "motivo": "Cambió de planes"}
    assert cancelar(cliente, admin, e, datos).status_code == 200

    def abonos(corte):
        return _grupo(cliente, admin, "encargos", corte, corte).json()["abonos_sin_entregar"]

    assert abonos(HOY) == 40000
    assert abonos(date(2026, 11, 12)) == 0


def test_grupos_vacios(cliente, admin):
    for g in GRUPOS:
        r = _grupo(cliente, admin, g, "2020-01-01", "2020-01-07")
        assert r.status_code == 200, (g, r.text)
    assert (
        _grupo(cliente, admin, "ganancia", "2020-01-01", "2020-01-07").json()["cascada"]["utilidad"]
        == 0
    )


def _sin_floats(valor, ruta="$"):
    assert not isinstance(valor, float), ruta
    if isinstance(valor, dict):
        for k, v in valor.items():
            _sin_floats(v, f"{ruta}.{k}")
    elif isinstance(valor, list):
        for i, v in enumerate(valor):
            _sin_floats(v, f"{ruta}[{i}]")


def test_sin_floats_en_respuestas(cliente, admin, carta, metodos, reloj):
    _abrir(cliente, admin, reloj)
    vendida(cliente, admin, venta_mockup(carta, metodos))
    for g in GRUPOS:
        _sin_floats(_grupo(cliente, admin, g).json(), g)
    _sin_floats(cliente.get(f"{API}/reportes/dashboard", headers=admin).json(), "dashboard")
    for tipo in (
        "ventas", "gastos", "flujo-caja", "utilidad-productos", "inventario-valorizado",
        "mermas", "propinas", "domicilios", "descuentos-cortesias", "ingresos-cancelacion",
        "cierres",
    ):  # fmt: skip
        r = reporte(cliente, admin, tipo, HOY, HOY)
        assert r.status_code == 200, (tipo, r.text)
        _sin_floats(r.json(), tipo)


def test_produccion_solo_ve_lo_suyo(cliente, crear_usuario, login):
    produccion = login(crear_usuario("produccion", email="prod@zuquis.co"))
    assert set(_grupo(cliente, produccion, "productos").json()) == {"producido_vendido"}
    assert set(_grupo(cliente, produccion, "gastos").json()) == {"mermas"}
    assert _grupo(cliente, produccion, "ganancia").status_code == 403
    assert _grupo(cliente, produccion, "cajeros").status_code == 403
