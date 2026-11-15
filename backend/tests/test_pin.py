"""PIN corto para cambio rápido de cajero y para autorizar descuentos (#35)."""

import pytest

from tests.conftest import CLAVE, rol_base
from tests.fixtures_ventas import API, vender

pytestmark = pytest.mark.usefixtures("caja_abierta")


@pytest.fixture
def cajera(crear_usuario, login, cliente):
    usuario = crear_usuario("cajero", nombre="Cajera Ana")
    headers = login(usuario)
    r = cliente.put(f"{API}/auth/pin", headers=headers, json={"clave_actual": CLAVE, "pin": "4821"})
    assert r.status_code == 204, r.text
    return usuario


def cambiar(cliente, headers, usuario, pin):
    return cliente.post(
        f"{API}/auth/pin", headers=headers, json={"usuario_id": str(usuario.id), "pin": pin}
    )


def test_pin_de_4_a_6_digitos_y_con_la_contrasena(cliente, crear_usuario, login):
    headers = login(crear_usuario("cajero"))
    for pin in ("123", "1234567", "12a4"):
        assert (
            cliente.put(
                f"{API}/auth/pin", headers=headers, json={"clave_actual": CLAVE, "pin": pin}
            ).status_code
            == 422
        )
    r = cliente.put(
        f"{API}/auth/pin", headers=headers, json={"clave_actual": "otra", "pin": "1234"}
    )
    assert (r.status_code, r.json()["codigo"]) == (401, "CREDENCIALES_INVALIDAS")


def test_la_lista_de_cajeros_muestra_quien_tiene_pin(cliente, admin, cajera):
    r = cliente.get(f"{API}/auth/cajeros", headers=admin)
    assert r.status_code == 200, r.text
    assert {"id": str(cajera.id), "nombre": "Cajera Ana"} in r.json()


def test_cambiar_de_cajero_con_pin(cliente, admin, cajera):
    r = cambiar(cliente, admin, cajera, "4821")
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["nombre"] == "Cajera Ana"
    nuevo = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert cliente.get(f"{API}/auth/me", headers=nuevo).json()["usuario"]["id"] == str(cajera.id)


def test_las_ventas_quedan_a_nombre_de_quien_ingreso_el_pin(cliente, admin, cajera, carta, metodos):
    token = cambiar(cliente, admin, cajera, "4821").json()["access_token"]
    datos = {
        "tipo_servicio": "local",
        "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "1"}],
        "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 4500}],
    }
    v = vender(cliente, {"Authorization": f"Bearer {token}"}, datos).json()
    assert v["cajero"] == "Cajera Ana"


def test_pin_equivocado_bloquea_tras_varios_intentos(cliente, admin, cajera):
    for _ in range(5):
        r = cambiar(cliente, admin, cajera, "0000")
        assert r.status_code == 401
    r = cambiar(cliente, admin, cajera, "4821")
    assert (r.status_code, r.json()["codigo"]) == (423, "USUARIO_BLOQUEADO")


def test_sin_sesion_en_el_equipo_no_se_cambia(cliente, cajera):
    assert cambiar(cliente, {}, cajera, "4821").status_code == 401


def test_autorizar_descuento_con_pin(cliente, admin, carta, metodos, crear_usuario, login, db):
    jefe = crear_usuario("admin", nombre="Jefe")
    cliente.put(f"{API}/auth/pin", headers=login(jefe), json={"clave_actual": CLAVE, "pin": "9090"})
    rol = rol_base(db, "cajero")
    cliente.patch(
        f"{API}/configuracion", headers=admin, json={"tope_descuento_por_rol": {str(rol.id): "10"}}
    )
    cajero = login(crear_usuario("cajero"))
    datos = {
        "tipo_servicio": "local",
        "items": [{"producto_id": carta["malteada"]["id"], "cantidad": "1"}],
        "descuento": {"tipo": "porcentaje", "valor": "20", "motivo": "Cliente frecuente"},
        "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 12800}],
        "autorizacion": {"usuario_id": str(jefe.id), "pin": "9090"},
    }
    r = vender(cliente, cajero, datos)
    assert r.status_code == 201, r.text
    assert r.json()["descuento_autorizado_por"] == str(jefe.id)
