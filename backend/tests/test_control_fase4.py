"""Caso de control de la Fase 4 (#49): una semana completa cuadra al peso en todos los reportes,
el dashboard y la galería. Los valores salen de tests/control/fase4.md, calculados a mano."""

from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from app.demo.semana import contexto, generar_semana
from tests.conftest import SEDE_PRINCIPAL
from tests.fixtures_reportes import reporte, seccion
from tests.fixtures_ventas import API

LUNES, DOMINGO = date(2026, 11, 9), date(2026, 11, 15)


def _r(cliente, admin, tipo, desde=LUNES, hasta=DOMINGO, **params):
    r = reporte(cliente, admin, tipo, desde, hasta, **params)
    assert r.status_code == 200, (tipo, r.text)
    return r.json() if params.get("formato") is None else r


def _g(cliente, admin, grupo):
    r = cliente.get(
        f"{API}/reportes/graficos",
        headers=admin,
        params={"grupo": grupo, "desde": str(LUNES), "hasta": str(DOMINGO)},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _filas(rep, titulo, clave, valor):
    return {f[clave]: f[valor] for f in seccion(rep, titulo)["filas"]}


def test_semana_cuadra_al_peso(cliente, admin, crear_usuario, db, reloj):
    usuario = crear_usuario("admin", email="semana@zuquis.co")
    generar_semana(db, contexto(usuario.id, SEDE_PRINCIPAL), LUNES)
    db.commit()

    # --- Ventas ---
    ventas = _r(cliente, admin, "ventas")
    resumen = _filas(ventas, "Resumen", "concepto", "valor")
    assert resumen["Ventas (sin propinas ni domicilios)"] == 118000
    assert resumen["Número de ventas"] == 9
    assert resumen["Costo de insumos"] == 9700
    assert resumen["Descuentos y cortesías"] == 6000
    assert resumen["Costo de las cortesías"] == 600
    assert resumen["Propinas (de terceros)"] == 1000
    assert resumen["Domicilios (de terceros)"] == 3000
    assert resumen["Ingresos por cancelación"] == 6000
    assert resumen["Ventas anuladas"] == 1
    assert seccion(ventas, "Por producto")["totales"]["ventas"] == 118000

    # --- Utilidad por producto ---
    utilidad = _r(cliente, admin, "utilidad-productos")
    por_producto = {
        f["producto"]: (f["unidades"], f["ventas"], f["costo"])
        for f in seccion(utilidad, "Por producto")["filas"]
    }
    assert por_producto["Pan de bono"] == ("22.0000", 44000, 6700)
    assert por_producto["Café con leche"] == ("5.0000", 25000, 3000)
    assert por_producto["Torta de chocolate 2 lb"] == ("1.0000", 50000, 0)
    assert seccion(utilidad, "Por producto")["totales"] == {
        "ventas": 118000,
        "costo": 9700,
        "utilidad": 108300,
    }

    # --- Gastos, mermas, inventario ---
    assert seccion(_r(cliente, admin, "gastos"), "Por categoría")["totales"]["monto"] == 512000
    mermas = _r(cliente, admin, "mermas")
    assert _filas(mermas, "Por motivo", "motivo", "costo") == {"Dañado": 2000, "Vencido": 700}
    valorizado = _r(cliente, admin, "inventario-valorizado")
    assert seccion(valorizado, "Por lote")["totales"]["valor"] == 96000

    # --- Dinero de terceros, cancelaciones, cierres ---
    assert seccion(_r(cliente, admin, "propinas"), "Por día")["totales"]["propinas"] == 1000
    dom = _r(cliente, admin, "domicilios")
    assert _filas(dom, "Por domiciliario", "domiciliario", "valor") == {"Carlos": 3000}
    canc = _r(cliente, admin, "ingresos-cancelacion")
    assert seccion(canc, "Encargos cancelados")["totales"] == {"devuelto": 4000, "retenido": 6000}
    cierres = _r(cliente, admin, "cierres")
    assert seccion(cierres, "Arqueos")["totales"]["diferencia"] == -2000
    desc = _r(cliente, admin, "descuentos-cortesias")
    assert seccion(desc, "Detalle")["totales"] == {"descuento": 6000, "costo_cortesia": 600}

    # --- Flujo de caja ---
    flujo = _r(cliente, admin, "flujo-caja")
    assert seccion(flujo, "Por día")["totales"]["entra"] == 144000
    assert seccion(flujo, "Por día")["totales"]["sale"] == 31000 + 509000
    assert seccion(flujo, "Fuera de caja")["totales"]["sale"] == 509000

    # --- PUC ---
    puc = _filas(_r(cliente, admin, "puc"), "Por cuenta", "cuenta", "monto")
    assert puc == {
        "1105": 103000,
        "1110": 29000,
        "2380": 4000,
        "2805": 30000,
        "4120": 119000,
        "4175": 1000,
        "4295": 6000,
        "5120": 500000,
        "5195": 12000,
        "5295": 3300,
        "6120": 9700,
    }

    # --- Galería ---
    ganancia = _g(cliente, admin, "ganancia")
    assert ganancia["cascada"] == {
        "ventas": 118000,
        "costo_insumos": 9700,
        "regalado": 600,
        "gastos": 512000,
        "mermas": 2700,
        "ingresos_cancelacion": 6000,
        "utilidad": -401000,
    }
    assert ganancia["costo_pct"] == [
        {"semana": "2026-W46", "ventas": 118000, "costo": 9700, "pct": "8.22"}
    ]
    productos = _g(cliente, admin, "productos")
    pan = next(p for p in productos["producido_vendido"] if p["producto"] == "Pan de bono")
    assert (pan["producido"], pan["vendido"]) == ("40.0000", "22.0000")
    gastos = _g(cliente, admin, "gastos")
    assert gastos["por_pagar"] == {
        "con_fecha": {"vencidas": 40000, "esta_semana": 0, "proximas": 0},
        "sin_fecha": {"d0_15": 60000, "d16_30": 0, "d30_mas": 0},
    }
    encargos = _g(cliente, admin, "encargos")
    assert encargos["por_semana"] == [{"semana": "2026-W46", "entregados": 1, "cancelados": 1}]
    assert encargos["abonos_sin_entregar"] == 0
    assert encargos["clientes_top"] == [{"cliente": "Ana Gómez", "encargos": 1, "total": 50000}]
    cajeros = _g(cliente, admin, "cajeros")["por_cajero"]
    assert [
        (c["vendido"], c["descuentos"], c["cortesias"], c["diferencia_cierres"]) for c in cajeros
    ] == [(118000, 1000, 1, -2000)]

    # --- Excel: la suma coincide con el JSON ---
    xlsx = _r(cliente, admin, "ventas", formato="xlsx")
    hoja = load_workbook(BytesIO(xlsx.content))["Por día"]
    assert (
        sum(
            row[2]
            for row in hoja.iter_rows(min_row=7, values_only=True)
            if row[0] and row[0] != "Total"
        )
        == 118000
    )

    # --- Dashboard del miércoles ---
    reloj("2026-11-11T21:00:00-05:00")
    d = cliente.get(f"{API}/reportes/dashboard", headers=admin).json()
    assert (d["ventas"], d["n_ventas"], d["gastos"], d["ganancia"], d["ticket_promedio"]) == (
        8000,
        1,
        0,
        6800,
        8000,
    )


def test_semilla_marca_datos_de_ejemplo(cliente, admin, crear_usuario, db):
    from app.demo.semana import sembrar_demo

    usuario = crear_usuario("admin", email="semilla@zuquis.co")
    sembrar_demo(db, usuario.id, SEDE_PRINCIPAL, LUNES)
    db.commit()
    assert cliente.get(f"{API}/reportes/dashboard", headers=admin).json()["datos_ejemplo"] is True


def test_semilla_rechaza_una_sede_con_ventas(crear_usuario, db):
    import pytest

    from app.demo.semana import SedeConVentas, sembrar_demo

    usuario = crear_usuario("admin", email="semilla2@zuquis.co")
    sembrar_demo(db, usuario.id, SEDE_PRINCIPAL, LUNES)
    with pytest.raises(SedeConVentas):
        sembrar_demo(db, usuario.id, SEDE_PRINCIPAL, LUNES)
