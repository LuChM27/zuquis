"""Reportes de la fase 4 (#46): base del módulo, cifras de ventas y reporte de ventas."""

from datetime import date

from app.modules.configuracion.models import Sede
from app.modules.reportes.cifras import descuento_global, totales, ventas_por
from app.modules.reportes.periodo import Periodo
from app.modules.usuarios.models import UsuarioRol
from tests.conftest import SEDE_PRINCIPAL, rol_base
from tests.fixtures_encargos import abonar, cancelar, crear_encargo, torta
from tests.fixtures_reportes import cortesia, malteada, reporte, seccion, vendida
from tests.fixtures_ventas import API, venta_mockup

HOY = date(2026, 11, 10)


def _dia(d: date = HOY) -> Periodo:
    return Periodo(sede_id=SEDE_PRINCIPAL, desde=d, hasta=d)


def _abrir(cliente, admin, reloj, momento="2026-11-10T09:00:00-05:00"):
    reloj(momento)
    r = cliente.post(f"{API}/caja/abrir", headers=admin, json={"base_inicial": 100000})
    assert r.status_code == 201, r.text


def _un_dia(cliente, admin, carta, metodos, reloj):
    """Venta del mockup ($46.500, propina $2.000, descuento $3.000, costo $10.650), una
    malteada sola por Nequi ($16.000, costo $4.200) y una cortesía (malteada al 100 %,
    costo $4.200)."""
    _abrir(cliente, admin, reloj)
    reloj("2026-11-10T15:10:00-05:00")
    vendida(cliente, admin, venta_mockup(carta, metodos))
    reloj("2026-11-10T16:20:00-05:00")
    vendida(cliente, admin, malteada(carta, metodos, pago=16000, metodo="Nequi"))
    reloj("2026-11-10T16:40:00-05:00")
    vendida(cliente, admin, cortesia(carta, metodos))


def test_totales_de_un_dia(cliente, admin, carta, metodos, reloj, db):
    _un_dia(cliente, admin, carta, metodos, reloj)
    assert totales(db, _dia()).model_dump() == {
        "ventas": 62500,
        "n_ventas": 3,
        "n_cortesias": 1,
        "costo_insumos": 14850,
        "costo_cortesias": 4200,
        "descuentos": 19000,
        "propinas": 2000,
        "domicilios": 0,
        "gastos": 0,
        "mermas": 0,
        "ingresos_cancelacion": 0,
        "anuladas": 0,
        "n_gastos": 0,
    }


def test_anuladas_no_suman(cliente, admin, carta, metodos, reloj, db):
    _abrir(cliente, admin, reloj)
    v = vendida(cliente, admin, malteada(carta, metodos, pago=16000))
    r = cliente.post(f"{API}/ventas/{v['id']}/anular", headers=admin, json={"motivo": "Error"})
    assert r.status_code == 200, r.text
    t = totales(db, _dia())
    assert (t.ventas, t.n_ventas, t.costo_insumos, t.anuladas) == (0, 0, 0, 1)


def test_venta_2330_cae_en_su_dia_local(cliente, admin, carta, metodos, reloj, db):
    _abrir(cliente, admin, reloj, "2026-11-10T23:00:00-05:00")
    reloj("2026-11-10T23:30:00-05:00")
    vendida(cliente, admin, malteada(carta, metodos, pago=16000))
    assert [(f.clave, f.ventas) for f in ventas_por(db, _dia(), "dia")] == [("2026-11-10", 16000)]
    assert [f.clave for f in ventas_por(db, _dia(), "hora")] == ["23"]
    assert totales(db, _dia(date(2026, 11, 11))).ventas == 0


def test_por_metodo_suma_pagos(cliente, admin, carta, metodos, reloj, db):
    _un_dia(cliente, admin, carta, metodos, reloj)
    filas = {f.etiqueta: f.ventas for f in ventas_por(db, _dia(), "metodo")}
    assert filas == {"Efectivo": 28500, "Nequi": 36000}


def test_por_categoria_producto_y_cajero(cliente, admin, carta, metodos, reloj, db):
    _un_dia(cliente, admin, carta, metodos, reloj)
    # Por producto y categoría: valor de las líneas antes del descuento sobre el total de la
    # venta ($3.000), sin cortesías (se reportan aparte). 49.500 + 16.000 − 3.000 = 62.500.
    categorias = {f.etiqueta: f.ventas for f in ventas_por(db, _dia(), "categoria")}
    assert sum(categorias.values()) == 65500
    assert descuento_global(db, _dia()) == 3000
    productos = {f.etiqueta: f.unidades for f in ventas_por(db, _dia(), "producto")}
    assert productos["Malteada de brownie"] == 2
    cajeros = ventas_por(db, _dia(), "cajero")
    assert [(f.ventas, f.n) for f in cajeros] == [(62500, 3)]


def test_reporte_de_ventas_json(cliente, admin, carta, metodos, reloj):
    _un_dia(cliente, admin, carta, metodos, reloj)
    r = reporte(cliente, admin, "ventas", HOY, HOY)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["tipo"] == "ventas"
    assert [s["titulo"] for s in cuerpo["secciones"]] == [
        "Resumen",
        "Por día",
        "Por producto",
        "Por categoría",
        "Por método de pago",
        "Por tipo de servicio",
        "Por cajero",
    ]
    assert seccion(cuerpo, "Por método de pago")["totales"]["ventas"] == 64500
    assert seccion(cuerpo, "Por día")["totales"]["ventas"] == 62500
    assert seccion(cuerpo, "Por producto")["totales"]["ventas"] == 62500
    assert seccion(cuerpo, "Por categoría")["totales"]["ventas"] == 62500


def test_rango_vacio_da_ceros(cliente, admin):
    r = reporte(cliente, admin, "ventas", "2020-01-01", "2020-01-02")
    assert r.status_code == 200, r.text
    assert all(f["valor"] == 0 for f in seccion(r.json(), "Resumen")["filas"])
    assert all(s["filas"] == [] for s in r.json()["secciones"][1:])


def test_rango_invalido(cliente, admin):
    r = reporte(cliente, admin, "ventas", "2026-11-10", "2026-11-09")
    assert r.status_code == 422
    assert "La fecha inicial no puede ser posterior a la final" in r.text
    r = reporte(cliente, admin, "ventas", "2025-01-01", "2026-02-05")
    assert r.status_code == 422
    assert "El rango no puede pasar de un año" in r.text


def test_tipo_desconocido_404(cliente, admin):
    assert reporte(cliente, admin, "inventado", HOY, HOY).status_code == 404


def test_sede_ajena_403(cliente, admin, db):
    otra = Sede(nombre="Sede Norte")
    db.add(otra)
    db.commit()
    assert reporte(cliente, admin, "ventas", HOY, HOY, sede_id=str(otra.id)).status_code == 403


def test_sede_propia_con_permiso(cliente, crear_usuario, login, db):
    yo = crear_usuario("admin")
    otra = Sede(nombre="Sede Norte")
    db.add(otra)
    db.flush()
    db.add(UsuarioRol(usuario_id=yo.id, rol_id=rol_base(db, "admin").id, sede_id=otra.id))
    db.commit()
    r = reporte(cliente, login(yo, SEDE_PRINCIPAL), "ventas", HOY, HOY, sede_id=str(otra.id))
    assert r.status_code == 200, r.text
    assert r.json()["sede"] == "Sede Norte"


def test_permisos_ventas(cliente, admin, carta, metodos, reloj, crear_usuario, login):
    produccion = login(crear_usuario("produccion", email="prod@zuquis.co"))
    assert reporte(cliente, produccion, "ventas", HOY, HOY).status_code == 403

    # Se inicia sesión antes de fijar el reloj: el token se vence con la hora real.
    cajero = login(crear_usuario("cajero", email="caja@zuquis.co"))
    _un_dia(cliente, admin, carta, metodos, reloj)
    r = reporte(cliente, cajero, "ventas", "2026-11-01", HOY)
    assert r.status_code == 200, r.text
    assert seccion(r.json(), "Por cajero")["totales"]["ventas"] == 62500


def test_cajero_sin_caja_abierta_ve_reporte_vacio(cliente, crear_usuario, login):
    cajero = login(crear_usuario("cajero", email="caja@zuquis.co"))
    r = reporte(cliente, cajero, "ventas", HOY, HOY)
    assert r.status_code == 200, r.text
    assert all(s["filas"] == [] for s in r.json()["secciones"][1:])


def test_cajero_no_ve_cifras_de_toda_la_sede(cliente, admin, cliente_a, metodos, reloj, db):
    """Con la caja limitada, los ingresos por cancelación y las mermas (de la sede) son 0."""
    _abrir(cliente, admin, reloj)
    e = crear_encargo(cliente, admin, torta(cliente_a["id"])).json()
    assert abonar(cliente, admin, e, 40000, metodos["Efectivo"]).status_code == 201
    datos = {"decision": "devuelve_parcial", "monto_devuelto": 25000, "motivo": "Cambio"}
    assert cancelar(cliente, admin, e, datos).status_code == 200
    assert totales(db, _dia()).ingresos_cancelacion == 15000
    sesion = cliente.get(f"{API}/caja/actual", headers=admin).json()["sesion"]["id"]
    p = Periodo(sede_id=SEDE_PRINCIPAL, desde=HOY, hasta=HOY, caja_sesion_id=sesion)
    assert (totales(db, p).mermas, totales(db, p).ingresos_cancelacion) == (0, 0)
