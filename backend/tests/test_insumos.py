"""Insumos, presentaciones y conversión (#17)."""

import uuid
from decimal import Decimal as D

import pytest

from app.core.deps import Contexto
from app.modules.inventario import motor
from app.modules.inventario.models import Presentacion
from app.modules.inventario.service import convertir
from app.shared.errores import ErrorNegocio
from tests.conftest import SEDE_PRINCIPAL

INSUMOS = "/api/v1/insumos"


@pytest.mark.parametrize(
    ("cantidad", "factor", "esperado"),
    [
        ("1", "50000", "50000"),  # Bulto 50 kg → g
        ("0.5", "1000", "500"),  # medio litro → ml
        ("2", "30", "60"),  # paquetes x 30 → und
        ("1.25", "2.5", "3.125"),  # factor no entero
        ("3", None, "3"),  # sin presentación: ya está en la unidad base
    ],
)
def test_conversion_a_unidad_base(cantidad, factor, esperado):
    p = Presentacion(nombre="x", factor=D(factor)) if factor else None
    assert convertir(D(cantidad), p) == D(esperado)


def test_conversion_con_mas_de_4_decimales_se_rechaza():
    with pytest.raises(ErrorNegocio):
        convertir(D("0.3333"), Presentacion(nombre="x", factor=D("0.5")))


def test_crear_insumo_con_presentaciones(cliente, admin):
    r = cliente.post(
        INSUMOS,
        headers=admin,
        json={
            "nombre": "Harina de trigo",
            "unidad_base": "g",
            "stock_minimo": "5000",
            "presentaciones": [
                {"nombre": "Bulto 50 kg", "factor": "50000"},
                {"nombre": "Kilo", "factor": "1000"},
            ],
        },
    )
    assert r.status_code == 201, r.json()
    datos = r.json()
    assert datos["stock_minimo"] == "5000.0000"
    assert [(p["nombre"], p["factor"]) for p in datos["presentaciones"]] == [
        ("Kilo", "1000.0000"),
        ("Bulto 50 kg", "50000.0000"),
    ]
    assert any(i["nombre"] == "Harina de trigo" for i in cliente.get(INSUMOS, headers=admin).json())


def test_unidad_desconocida_y_nombre_duplicado(cliente, admin):
    r = cliente.post(INSUMOS, headers=admin, json={"nombre": "Leche", "unidad_base": "litros"})
    assert r.json()["codigo"] == "UNIDAD_DESCONOCIDA"
    cliente.post(INSUMOS, headers=admin, json={"nombre": "Leche", "unidad_base": "ml"})
    r = cliente.post(INSUMOS, headers=admin, json={"nombre": "Leche", "unidad_base": "ml"})
    assert (r.status_code, r.json()["codigo"]) == (409, "NOMBRE_DUPLICADO")


def test_no_se_cambia_la_unidad_de_un_insumo_con_movimientos(cliente, admin, db, crear_usuario):
    insumo = cliente.post(
        INSUMOS, headers=admin, json={"nombre": "Azúcar", "unidad_base": "g"}
    ).json()
    # Sin movimientos sí se puede.
    r = cliente.patch(f"{INSUMOS}/{insumo['id']}", headers=admin, json={"unidad_base": "und"})
    assert r.status_code == 200
    ctx = Contexto(usuario_id=crear_usuario("admin").id, sede_id=SEDE_PRINCIPAL)
    motor.crear_lote(
        db,
        ctx,
        tipo_item="insumo",
        item_id=uuid.UUID(insumo["id"]),
        origen="compra",
        origen_id=None,
        cantidad=D("10"),
        costo_unitario=D("1"),
        tipo_mov="compra",
        referencia_tipo="compra",
        referencia_id=uuid.uuid4(),
    )
    db.commit()
    r = cliente.patch(f"{INSUMOS}/{insumo['id']}", headers=admin, json={"unidad_base": "g"})
    assert (r.status_code, r.json()["codigo"]) == (409, "UNIDAD_CON_MOVIMIENTOS")
    # Otros cambios siguen permitidos.
    r = cliente.patch(f"{INSUMOS}/{insumo['id']}", headers=admin, json={"stock_minimo": "20"})
    assert r.json()["stock_minimo"] == "20.0000"


def test_presentaciones_se_agregan_y_desactivan(cliente, admin):
    insumo = cliente.post(
        INSUMOS, headers=admin, json={"nombre": "Huevos", "unidad_base": "und"}
    ).json()
    p = cliente.post(
        f"{INSUMOS}/{insumo['id']}/presentaciones",
        headers=admin,
        json={"nombre": "Panal x 30", "factor": "30"},
    ).json()
    r = cliente.patch(
        f"{INSUMOS}/{insumo['id']}/presentaciones/{p['id']}", headers=admin, json={"activa": False}
    )
    assert r.json()["activa"] is False


def test_permisos_de_insumos(cliente, crear_usuario, login):
    produccion = login(crear_usuario("produccion"))
    cajero = login(crear_usuario("cajero"))
    assert (
        cliente.post(
            INSUMOS, headers=produccion, json={"nombre": "Sal", "unidad_base": "g"}
        ).status_code
        == 201
    )
    assert cliente.get(INSUMOS, headers=cajero).status_code == 403
    assert (
        cliente.post(
            INSUMOS, headers=cajero, json={"nombre": "Sal2", "unidad_base": "g"}
        ).status_code
        == 403
    )
