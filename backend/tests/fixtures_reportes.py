"""Ayudas compartidas por las pruebas de reportes (fase 4)."""

from datetime import date, datetime

import pytest

from app.shared import fechas
from tests.fixtures_ventas import API, vender


@pytest.fixture
def reloj():
    """reloj("2026-11-09T15:00:00-05:00") fija la hora del sistema hasta que termina la prueba."""

    def _fijar(momento: str) -> None:
        fechas.fijar_ahora(datetime.fromisoformat(momento))

    yield _fijar
    fechas.fijar_ahora(None)


def malteada(carta, metodos, descuento=None, pago=None, metodo="Efectivo", **extra):
    """Una malteada de $16.000 (costo $4.200) con el descuento indicado."""
    datos = {
        "tipo_servicio": "local",
        "items": [{"producto_id": carta["malteada"]["id"], "cantidad": "1"}],
        "descuento": descuento,
        "pagos": [{"metodo_pago_id": metodos[metodo], "monto": pago}] if pago else [],
    }
    return datos | extra


def cortesia(carta, metodos):
    return malteada(carta, metodos, {"tipo": "porcentaje", "valor": "100", "motivo": "Cumpleaños"})


def vendida(cliente, headers, datos) -> dict:
    r = vender(cliente, headers, datos)
    assert r.status_code == 201, r.text
    return r.json()


def reporte(cliente, headers, tipo, desde: date | str, hasta: date | str, **params):
    return cliente.get(
        f"{API}/reportes/{tipo}",
        headers=headers,
        params={"desde": str(desde), "hasta": str(hasta)} | params,
    )


def seccion(reporte_json: dict, titulo: str) -> dict:
    return next(s for s in reporte_json["secciones"] if s["titulo"] == titulo)
