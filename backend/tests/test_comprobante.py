"""Comprobante interno en PDF y resumen de cierre (#33, RF-14, RF-20).

El HTML se prueba en cualquier equipo; el PDF solo donde WeasyPrint tiene sus librerías
(imagen Docker y CI). En Windows sin GTK esas pruebas aparecen como omitidas, no como pasadas.
"""

import pytest

from app.core.deps import Contexto
from app.modules.ventas import comprobante, service
from app.shared.pdf import pdf_disponible
from tests.conftest import SEDE_PRINCIPAL
from tests.fixtures_ventas import API, vender, venta_mockup

pytestmark = pytest.mark.usefixtures("caja_abierta")
solo_con_pdf = pytest.mark.skipif(
    not pdf_disponible(), reason="WeasyPrint sin Pango en este equipo"
)


@pytest.fixture
def venta(cliente, admin, carta, metodos):
    datos = venta_mockup(carta, metodos)
    datos["pagos"] = [{"metodo_pago_id": metodos["Efectivo"], "monto": 48500, "recibido": 50000}]
    return vender(cliente, admin, datos).json()


def html_de(db, venta, formato="media_carta"):
    ctx = Contexto(usuario_id=None, sede_id=SEDE_PRINCIPAL)
    v = service.salida(db, service.obtener(db, ctx, venta["id"]))
    return comprobante.html(db, ctx, v, formato)


def test_el_comprobante_trae_todo_lo_de_la_venta(db, venta):
    h = html_de(db, venta)
    for texto in (
        f"Comprobante n.º {venta['numero']:04d}",
        "Zuqui",
        "1 × Malteada de brownie",
        "+ Bola de helado",
        "Sin hielo",
        "2 × Pastel de pollo",
        "$49.500",
        "Descuento · Cliente frecuente",
        "−$3.000",
        "$46.500",
        "Propina (aparte, no es venta)",
        "$48.500",
        "recibido $50.000",
        "Cambio",
        "$1.500",
        "Documento interno, no es factura electrónica.",
    ):
        assert texto in h, texto


def test_ancho_configurable(db, venta):
    assert "size: 80mm" in html_de(db, venta, "80mm")
    assert "size: 216mm 279mm" in html_de(db, venta, "carta")


def test_anulada_lleva_marca_de_agua(cliente, admin, db, venta):
    cliente.post(
        f"{API}/ventas/{venta['id']}/anular", headers=admin, json={"motivo": "Error de cobro"}
    )
    h = html_de(db, venta)
    assert 'class="anulado">ANULADA' in h and "Error de cobro" in h


@solo_con_pdf
def test_el_pdf_se_descarga(cliente, admin, venta):
    r = cliente.get(
        f"{API}/ventas/{venta['id']}/comprobante", headers=admin, params={"formato": "carta"}
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


@solo_con_pdf
def test_resumen_de_cierre_en_pdf(cliente, admin, metodos):
    cliente.post(
        f"{API}/caja/cerrar",
        headers=admin,
        json={"contado": [{"metodo_pago_id": metodos["Efectivo"], "contado": 100000}]},
    )
    sesion = cliente.get(f"{API}/caja/sesiones", headers=admin).json()["items"][0]
    r = cliente.get(f"{API}/caja/sesiones/{sesion['id']}/resumen", headers=admin)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


@pytest.mark.skipif(pdf_disponible(), reason="Solo aplica donde no hay WeasyPrint")
def test_sin_weasyprint_responde_503(cliente, admin, venta):
    r = cliente.get(f"{API}/ventas/{venta['id']}/comprobante", headers=admin)
    assert (r.status_code, r.json()["codigo"]) == (503, "PDF_NO_DISPONIBLE")
