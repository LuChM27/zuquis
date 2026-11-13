"""Descuentos y cortesías con tope por rol y autorización (#30, RF-11, RN-16, RN-17)."""

import uuid
from decimal import Decimal as D

import pytest
from sqlalchemy import select

from app.modules.auditoria.models import Auditoria
from app.modules.auth.models import Usuario
from tests.conftest import CLAVE, rol_base
from tests.fixtures_ventas import stock, vender

API = "/api/v1"


@pytest.fixture
def cajero(cliente, admin, crear_usuario, login, db):
    """Cajero con tope de descuento del 10 % y su caja abierta."""
    rol = rol_base(db, "cajero")
    r = cliente.patch(
        f"{API}/configuracion", headers=admin, json={"tope_descuento_por_rol": {str(rol.id): "10"}}
    )
    assert r.status_code == 200, r.text
    headers = login(crear_usuario("cajero"))
    cliente.post(f"{API}/caja/abrir", headers=headers, json={"base_inicial": 0})
    return headers


@pytest.fixture
def jefe(crear_usuario):
    """Administrador que autoriza con su correo y contraseña."""
    return crear_usuario("admin", email=f"jefe-{uuid.uuid4().hex[:6]}@zuquis.test")


def malteada(carta, metodos, descuento=None, pago=None, **extra):
    """Una malteada de $16.000 con el descuento indicado sobre la venta."""
    datos = {
        "tipo_servicio": "local",
        "items": [{"producto_id": carta["malteada"]["id"], "cantidad": "1"}],
        "descuento": descuento,
        "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": pago}] if pago else [],
    }
    return datos | extra


def pct(valor, motivo="Cliente frecuente"):
    return {"tipo": "porcentaje", "valor": valor, "motivo": motivo}


def test_dentro_del_tope_no_pide_autorizacion(cliente, cajero, carta, metodos):
    r = vender(cliente, cajero, malteada(carta, metodos, pct("10"), 14400))
    assert r.status_code == 201, r.text
    assert (r.json()["descuento_total"], r.json()["total"]) == (1600, 14400)


def test_sobre_el_tope_exige_autorizacion(cliente, cajero, carta, metodos):
    r = vender(cliente, cajero, malteada(carta, metodos, pct("15"), 13600))
    assert (r.status_code, r.json()["codigo"]) == (403, "DESCUENTO_REQUIERE_AUTORIZACION")
    assert r.json()["detalle"]["tope"] == "10"


def test_con_credencial_de_administrador_se_aplica(cliente, cajero, carta, metodos, jefe, db):
    datos = malteada(
        carta, metodos, pct("15"), 13600, autorizacion={"email": jefe.email, "clave": CLAVE}
    )
    r = vender(cliente, cajero, datos)
    assert r.status_code == 201, r.text
    venta = r.json()
    assert (venta["descuento_total"], venta["descuento_autorizado_por"]) == (2400, str(jefe.id))
    registro = db.scalar(
        select(Auditoria).where(
            Auditoria.accion == "autorizar_descuento", Auditoria.entidad_id == venta["id"]
        )
    )
    assert registro is not None and registro.usuario_id == jefe.id


def test_credencial_equivocada_no_vende_y_cuenta_el_intento(
    cliente, cajero, carta, metodos, jefe, db
):
    datos = malteada(
        carta, metodos, pct("15"), 13600, autorizacion={"email": jefe.email, "clave": "equivocada"}
    )
    r = vender(cliente, cajero, datos)
    assert (r.status_code, r.json()["codigo"]) == (403, "AUTORIZACION_INVALIDA")
    db.expire_all()
    assert db.get(Usuario, jefe.id).intentos_fallidos == 1
    assert cliente.get(f"{API}/ventas", headers=cajero).json()["total"] == 0


def test_otro_cajero_no_puede_autorizar(cliente, cajero, carta, metodos, crear_usuario):
    otro = crear_usuario("cajero", email=f"otro-{uuid.uuid4().hex[:6]}@zuquis.test")
    datos = malteada(
        carta, metodos, pct("15"), 13600, autorizacion={"email": otro.email, "clave": CLAVE}
    )
    r = vender(cliente, cajero, datos)
    assert (r.status_code, r.json()["codigo"]) == (403, "AUTORIZACION_INVALIDA")


def test_el_administrador_aplica_cualquier_descuento(cliente, admin, carta, metodos, caja_abierta):
    r = vender(cliente, admin, malteada(carta, metodos, pct("50"), 8000))
    assert r.status_code == 201, r.text
    assert r.json()["descuento_autorizado_por"] is None


def test_porcentaje_redondea_a_peso_mitad_hacia_arriba(
    cliente, admin, carta, metodos, caja_abierta
):
    # 15 % de 16.000 = 2.400 exacto; 12,5 % de 16.000 = 2.000; 33,33 % = 5.332,8 → 5.333.
    r = vender(cliente, admin, malteada(carta, metodos, pct("33.33"), 16000 - 5333))
    assert r.status_code == 201, r.text
    assert r.json()["descuento_total"] == 5333


def test_descuento_por_item_y_por_venta(cliente, admin, carta, metodos, caja_abierta):
    datos = {
        "tipo_servicio": "local",
        "items": [
            {
                "producto_id": carta["malteada"]["id"],
                "cantidad": "1",
                "descuento": {"tipo": "valor", "valor": "1000", "motivo": "Se demoró"},
            },
            {"producto_id": carta["soda"]["id"], "cantidad": "1"},
        ],
        # 10 % sobre lo que queda: (15.000 + 12.000) × 10 % = 2.700.
        "descuento": pct("10", "Cliente frecuente"),
        "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 27000 - 2700}],
    }
    v = vender(cliente, admin, datos).json()
    assert (v["subtotal"], v["descuento_total"], v["total"]) == (28000, 3700, 24300)
    assert v["items"][0]["descuento"] == 1000 and v["items"][0]["subtotal"] == 15000
    assert v["descuento_motivo"] == "Cliente frecuente; Se demoró"


def test_descuento_sin_motivo_no_se_acepta(cliente, admin, carta, metodos, caja_abierta):
    r = vender(
        cliente,
        admin,
        malteada(carta, metodos, {"tipo": "valor", "valor": "1000", "motivo": ""}, 15000),
    )
    assert r.status_code == 422


def test_cortesia_deja_la_venta_en_cero_y_consume_inventario(
    cliente, admin, carta, metodos, caja_abierta, db
):
    leche_antes = stock(db, "insumo", carta["insumos"]["Leche venta"])
    r = vender(cliente, admin, malteada(carta, metodos, pct("100", "Cortesía cumpleaños")))
    assert r.status_code == 201, r.text
    v = r.json()
    assert (v["total"], v["cobrado"], v["pagos"], v["cortesia"]) == (0, 0, [], True)
    # RN-17: descuenta inventario y guarda su costo (se reporta como gasto de cortesía).
    assert v["costo_total"] == 4200
    assert stock(db, "insumo", carta["insumos"]["Leche venta"]) == leche_antes - D("300")


def test_cajero_con_cortesia_necesita_autorizacion(cliente, cajero, carta, metodos):
    r = vender(cliente, cajero, malteada(carta, metodos, pct("100", "Cortesía")))
    assert (r.status_code, r.json()["codigo"]) == (403, "DESCUENTO_REQUIERE_AUTORIZACION")
