"""Clientes (#39, RF-40): registro, búsqueda rápida, teléfono repetido e historial."""

import pytest

from app.modules.clientes.service import normalizar_telefono
from app.shared.errores import ErrorNegocio
from tests.fixtures_encargos import crear_encargo, torta
from tests.fixtures_ventas import API, post, vender


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("300 123 4567", "3001234567"),
        ("+57 300-123-4567", "3001234567"),
        ("(605) 282 1234", "6052821234"),
        ("", None),
        (None, None),
    ],
)
def test_normaliza_el_telefono(entrada, esperado):
    assert normalizar_telefono(entrada) == esperado


def test_un_telefono_muy_corto_se_rechaza():
    with pytest.raises(ErrorNegocio) as exc:
        normalizar_telefono("12345")
    assert exc.value.codigo == "TELEFONO_INVALIDO"


def test_crear_guarda_el_telefono_normalizado_y_la_autorizacion(cliente, admin, cliente_a):
    assert cliente_a["telefono"] == "3001234567"
    assert cliente_a["autoriza_datos"] is True
    assert cliente_a["autorizo_en"] is not None


def test_telefono_repetido_advierte_pero_no_bloquea(cliente, admin, cliente_a):
    datos = {"nombre": "Otra persona", "telefono": "+57 3001234567"}
    r = cliente.post(f"{API}/clientes", headers=admin, json=datos)
    assert (r.status_code, r.json()["codigo"]) == (409, "TELEFONO_REPETIDO")
    assert r.json()["detalle"]["cliente"]["id"] == cliente_a["id"]

    r = cliente.post(
        f"{API}/clientes", headers=admin, json=datos | {"permitir_telefono_repetido": True}
    )
    assert r.status_code == 201, r.text


def test_buscar_por_nombre_o_por_telefono(cliente, admin, cliente_a):
    post(cliente, admin, "/clientes", {"nombre": "Beatriz Gómez", "telefono": "3159998877"})

    def buscar(q):
        r = cliente.get(f"{API}/clientes", headers=admin, params={"q": q})
        return [c["nombre"] for c in r.json()["items"]]

    assert buscar("beat") == ["Beatriz Gómez"]
    assert buscar("300 123") == ["Cliente A"]
    assert buscar("9998") == ["Beatriz Gómez"]
    assert buscar("nadie") == []


def test_editar_cambia_datos_y_desactiva(cliente, admin, cliente_a):
    r = cliente.patch(
        f"{API}/clientes/{cliente_a['id']}",
        headers=admin,
        json={"direccion": "Calle 17 # 11-87", "autoriza_datos": False},
    )
    assert r.status_code == 200, r.text
    assert (r.json()["direccion"], r.json()["autorizo_en"]) == ("Calle 17 # 11-87", None)

    cliente.patch(f"{API}/clientes/{cliente_a['id']}", headers=admin, json={"activo": False})
    assert cliente.get(f"{API}/clientes", headers=admin).json()["items"] == []


def test_el_cajero_gestiona_clientes_y_produccion_no(cliente, crear_usuario, login):
    cajero = login(crear_usuario("cajero"))
    assert (
        cliente.post(f"{API}/clientes", headers=cajero, json={"nombre": "Cliente B"}).status_code
        == 201
    )
    cocina = login(crear_usuario("produccion"))
    assert cliente.get(f"{API}/clientes", headers=cocina).status_code == 403


def test_historial_reune_ventas_encargos_y_domicilios(
    cliente, admin, cliente_a, domiciliario, carta, metodos, caja_abierta
):
    venta = vender(
        cliente,
        admin,
        {
            "tipo_servicio": "domicilio",
            "cliente_id": cliente_a["id"],
            "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "2"}],
            "valor_domicilio": 4000,
            "domicilio": {"domiciliario_id": domiciliario["id"], "direccion": "Cra 10 # 5-20"},
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 13000}],
        },
    )
    assert venta.status_code == 201, venta.text
    assert venta.json()["cliente"] == "Cliente A"
    assert crear_encargo(cliente, admin, torta(cliente_a["id"])).status_code == 201

    h = cliente.get(f"{API}/clientes/{cliente_a['id']}/historial", headers=admin).json()
    assert [(v["numero"], v["total"]) for v in h["ventas"]] == [(venta.json()["numero"], 9000)]
    assert [(e["descripcion"], e["total"]) for e in h["encargos"]] == [
        ("Torta de cumpleaños 1 lb · vainilla con fresas", 90000)
    ]
    assert [(d["direccion"], d["valor"]) for d in h["domicilios"]] == [("Cra 10 # 5-20", 4000)]
    assert h["total_comprado"] == 9000


def test_vender_a_un_cliente_que_no_existe_falla(cliente, admin, carta, metodos, caja_abierta):
    r = vender(
        cliente,
        admin,
        {
            "cliente_id": "00000000-0000-0000-0000-00000000abcd",
            "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "1"}],
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 4500}],
        },
    )
    assert (r.status_code, r.json()["codigo"]) == (404, "NO_ENCONTRADO")
