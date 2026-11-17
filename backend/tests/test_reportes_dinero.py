"""Reportes de dinero de la fase 4 (#46): gastos, flujo de caja, cierres, descuentos,
domicilios, propinas y cancelaciones. Valores calculados a mano en cada prueba."""

from datetime import date

from app.modules.reportes.dinero import flujo, gastos_por
from app.modules.reportes.periodo import Periodo
from tests.conftest import SEDE_PRINCIPAL
from tests.fixtures_encargos import abonar, cancelar, crear_encargo, torta
from tests.fixtures_reportes import malteada, reporte, seccion, vendida
from tests.fixtures_ventas import API, post

HOY = date(2026, 11, 10)
P = Periodo(sede_id=SEDE_PRINCIPAL, desde=HOY, hasta=HOY)


def _abrir(cliente, admin, reloj):
    reloj("2026-11-10T09:00:00-05:00")
    r = cliente.post(f"{API}/caja/abrir", headers=admin, json={"base_inicial": 100000})
    assert r.status_code == 201, r.text


def _categoria(cliente, admin, nombre="Aseo y cafetería"):
    cats = cliente.get(f"{API}/categorias-gasto", headers=admin).json()
    return next(c for c in cats if c["nombre"] == nombre)["id"]


def _gasto(cliente, admin, metodo_id, monto, fuente, categoria=None):
    return post(
        cliente,
        admin,
        "/gastos",
        {
            "fecha": str(HOY),
            "categoria_id": categoria or _categoria(cliente, admin),
            "descripcion": f"Gasto de {fuente}",
            "monto": monto,
            "metodo_pago_id": metodo_id,
            "fuente": fuente,
        },
    )


def test_gastos_por_categoria_y_fuente(cliente, admin, metodos, reloj, db):
    _abrir(cliente, admin, reloj)
    _gasto(cliente, admin, metodos["Efectivo"], 20000, "caja")
    _gasto(cliente, admin, metodos["Bancolombia"], 50000, "banco")
    filas = gastos_por(db, P)
    assert sorted((f.fuente, f.monto) for f in filas) == [("banco", 50000), ("caja", 20000)]
    r = reporte(cliente, admin, "gastos", HOY, HOY)
    assert r.status_code == 200, r.text
    assert seccion(r.json(), "Por categoría")["totales"]["monto"] == 70000
    assert seccion(r.json(), "Por fuente")["totales"]["monto"] == 70000


def test_gasto_anulado_no_suma(cliente, admin, metodos, reloj, db):
    _abrir(cliente, admin, reloj)
    g = _gasto(cliente, admin, metodos["Efectivo"], 20000, "caja")
    r = cliente.post(f"{API}/gastos/{g['id']}/anular", headers=admin, json={"motivo": "Repetido"})
    assert r.status_code == 200, r.text
    assert gastos_por(db, P) == []


def test_flujo_incluye_fuera_de_caja_sin_duplicar(cliente, admin, carta, metodos, reloj, db):
    _abrir(cliente, admin, reloj)
    vendida(
        cliente,
        admin,
        malteada(carta, metodos, pago=10000, descuento=None)
        | {
            "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "2"}],
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 9000}],
        },
    )
    _gasto(cliente, admin, metodos["Efectivo"], 3000, "caja")
    _gasto(cliente, admin, metodos["Bancolombia"], 5000, "banco")
    filas = flujo(db, P)
    assert sum(f.entra for f in filas) == 9000
    assert sum(f.sale for f in filas) == 8000
    assert sum(f.sale for f in filas if not f.en_caja) == 5000
    assert [f.tipo for f in filas if f.tipo == "gasto" and f.en_caja] == ["gasto"]


def test_flujo_por_titular(cliente, admin, carta, metodos, reloj):
    dueno = post(
        cliente, admin, "/metodos-pago", {"nombre": "Nequi de la dueña", "titular": "dueno"}
    )
    _abrir(cliente, admin, reloj)
    vendida(
        cliente,
        admin,
        {
            "tipo_servicio": "local",
            "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "1"}],
            "propina": 2500,
            "pagos": [{"metodo_pago_id": dueno["id"], "monto": 7000}],
        },
    )
    r = reporte(cliente, admin, "flujo-caja", HOY, HOY)
    assert r.status_code == 200, r.text
    titulares = {f["titular"]: f["entra"] for f in seccion(r.json(), "Por titular")["filas"]}
    assert titulares == {"Dueño": 7000}


def test_cierre_con_diferencia_asignada_a_quien_cerro(cliente, admin, carta, metodos, reloj):
    _abrir(cliente, admin, reloj)
    vendida(cliente, admin, malteada(carta, metodos, pago=16000))
    vista = cliente.get(f"{API}/caja/actual/cierre", headers=admin).json()
    contado = [
        {
            "metodo_pago_id": a["metodo_pago_id"],
            "contado": a["esperado"] - (2000 if a["metodo"] == "Efectivo" else 0),
        }
        for a in vista["arqueo"]
    ]
    reloj("2026-11-10T21:00:00-05:00")
    r = cliente.post(
        f"{API}/caja/cerrar",
        headers=admin,
        json={"contado": contado, "observacion": "Faltaron $2.000"},
    )
    assert r.status_code == 200, r.text
    r = reporte(cliente, admin, "cierres", HOY, HOY)
    assert r.status_code == 200, r.text
    efectivo = next(f for f in seccion(r.json(), "Arqueos")["filas"] if f["metodo"] == "Efectivo")
    assert (efectivo["esperado"], efectivo["contado"], efectivo["diferencia"]) == (
        116000,
        114000,
        -2000,
    )
    assert efectivo["cerrada_por"] == "Prueba"


def test_ingreso_por_cancelacion_por_fecha_de_cancelacion(
    cliente, admin, cliente_a, metodos, reloj
):
    _abrir(cliente, admin, reloj)
    e = crear_encargo(cliente, admin, torta(cliente_a["id"])).json()
    assert abonar(cliente, admin, e, 40000, metodos["Efectivo"]).status_code == 201
    r = cancelar(
        cliente,
        admin,
        e,
        {"decision": "devuelve_parcial", "monto_devuelto": 25000, "motivo": "Cambió de planes"},
    )
    assert r.status_code == 200, r.text
    r = reporte(cliente, admin, "ingresos-cancelacion", HOY, HOY)
    assert r.status_code == 200, r.text
    filas = seccion(r.json(), "Encargos cancelados")["filas"]
    assert [(f["devuelto"], f["retenido"]) for f in filas] == [(25000, 15000)]
    otro_dia = reporte(cliente, admin, "ingresos-cancelacion", "2026-11-11", "2026-11-11")
    assert seccion(otro_dia.json(), "Encargos cancelados")["filas"] == []


def test_descuento_registra_quien_autorizo(cliente, admin, carta, metodos, reloj):
    _abrir(cliente, admin, reloj)
    vendida(
        cliente,
        admin,
        malteada(carta, metodos, {"tipo": "valor", "valor": "1000", "motivo": "Amiga"}, 15000),
    )
    r = reporte(cliente, admin, "descuentos-cortesias", HOY, HOY)
    assert r.status_code == 200, r.text
    filas = seccion(r.json(), "Detalle")["filas"]
    assert [(f["descuento"], f["motivo"], f["cortesia"]) for f in filas] == [(1000, "Amiga", "No")]


def test_propinas_y_domicilios(cliente, admin, carta, metodos, reloj, domiciliario):
    _abrir(cliente, admin, reloj)
    vendida(
        cliente,
        admin,
        {
            "tipo_servicio": "domicilio",
            "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "1"}],
            "valor_domicilio": 5000,
            "propina": 1000,
            "domicilio": {"domiciliario_id": domiciliario["id"], "direccion": "Calle 1"},
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 10500}],
        },
    )
    prop = reporte(cliente, admin, "propinas", HOY, HOY).json()
    assert seccion(prop, "Por día")["totales"]["propinas"] == 1000
    dom = reporte(cliente, admin, "domicilios", HOY, HOY).json()
    assert [
        (f["domiciliario"], f["n"], f["valor"]) for f in seccion(dom, "Por domiciliario")["filas"]
    ] == [("Carlos", 1, 5000)]


def test_cajero_ve_solo_cierres_si_tiene_permiso(cliente, crear_usuario, login):
    cajero = login(crear_usuario("cajero", email="caja@zuquis.co"))
    assert reporte(cliente, cajero, "cierres", HOY, HOY).status_code == 200
    assert reporte(cliente, cajero, "gastos", HOY, HOY).status_code == 403
