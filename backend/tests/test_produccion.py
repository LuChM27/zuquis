"""Producción por lote (#21) y receta histórica (#20)."""

import uuid
from datetime import timedelta
from decimal import Decimal as D

import pytest

from app.core.deps import Contexto
from app.modules.inventario import motor
from app.modules.inventario.models import Lote
from app.shared.fechas import hoy
from tests.conftest import SEDE_PRINCIPAL

API = "/api/v1"


@pytest.fixture
def ctx(crear_usuario) -> Contexto:
    return Contexto(usuario_id=crear_usuario("admin").id, sede_id=SEDE_PRINCIPAL)


@pytest.fixture
def escenario(cliente, admin, db, ctx):
    """Pastel de pollo: receta de 12 con 600 g de harina y 900 g de pollo. Harina en dos lotes."""
    harina = cliente.post(
        f"{API}/insumos", headers=admin, json={"nombre": "Harina prod", "unidad_base": "g"}
    ).json()
    pollo = cliente.post(
        f"{API}/insumos", headers=admin, json={"nombre": "Pollo prod", "unidad_base": "g"}
    ).json()
    for insumo, cantidad, costo in (
        (harina, "400", "3"),
        (harina, "1000", "3.5"),
        (pollo, "3000", "14"),
    ):
        motor.crear_lote(
            db,
            ctx,
            tipo_item="insumo",
            item_id=uuid.UUID(insumo["id"]),
            origen="compra",
            origen_id=None,
            cantidad=D(cantidad),
            costo_unitario=D(costo),
            tipo_mov="compra",
            referencia_tipo="compra",
            referencia_id=uuid.uuid4(),
        )
    db.commit()
    salado = next(
        c["id"]
        for c in cliente.get(f"{API}/categorias", headers=admin).json()
        if c["nombre"] == "Salado"
    )
    producto = cliente.post(
        f"{API}/productos",
        headers=admin,
        json={
            "categoria_id": salado,
            "nombre": "Pastel de pollo prod",
            "tipo": "lote",
            "precio": 4500,
            "dias_vida_util": 2,
        },
    ).json()
    cliente.put(
        f"{API}/productos/{producto['id']}/receta",
        headers=admin,
        json={
            "rendimiento": "12",
            "items": [
                {"insumo_id": harina["id"], "cantidad": "600"},
                {"insumo_id": pollo["id"], "cantidad": "900"},
            ],
        },
    )
    return {"harina": harina, "pollo": pollo, "producto": producto}


def producir(cliente, headers, producto, cantidad="12", **extra):
    return cliente.post(
        f"{API}/producciones",
        headers=headers,
        json={"producto_id": producto["id"], "cantidad_producida": cantidad} | extra,
    )


def test_producir_12_con_harina_de_dos_lotes_da_el_costo_exacto(cliente, admin, escenario, db):
    r = producir(cliente, admin, escenario["producto"])
    assert r.status_code == 201, r.json()
    p = r.json()
    assert p["costo_total"] == 14500  # 400×3 + 200×3,5 + 900×14
    assert p["costo_unitario"] == "1208.333333"
    assert {c["insumo"]: (c["cantidad"], c["costo_total"]) for c in p["consumos"]} == {
        "Harina prod": ("600.0000", 1900),
        "Pollo prod": ("900.0000", 12600),
    }
    assert p["fecha_vencimiento"] == (hoy() + timedelta(days=2)).isoformat()
    lote = db.get(Lote, uuid.UUID(p["lote_resultante_id"]))
    assert (lote.tipo_item, lote.cantidad_disponible, lote.origen) == (
        "producto",
        D("12"),
        "produccion",
    )
    stock = cliente.get(f"{API}/productos/{escenario['producto']['id']}", headers=admin).json()[
        "stock"
    ]
    assert stock == "12.0000"


def test_producir_la_mitad_de_la_receta(cliente, admin, escenario):
    p = producir(cliente, admin, escenario["producto"], cantidad="6").json()
    # 300 g de harina del lote de $3 y 450 g de pollo
    assert p["costo_total"] == 900 + 6300
    assert p["costo_unitario"] == "1200.000000"


def test_sin_receta_vigente_es_error(cliente, admin):
    salado = next(
        c["id"]
        for c in cliente.get(f"{API}/categorias", headers=admin).json()
        if c["nombre"] == "Salado"
    )
    sin = cliente.post(
        f"{API}/productos",
        headers=admin,
        json={"categoria_id": salado, "nombre": "Sin receta", "tipo": "lote", "precio": 1},
    ).json()
    r = producir(cliente, admin, sin)
    assert r.json()["codigo"] == "SIN_RECETA"


def test_preparados_no_se_producen_por_lote(cliente, admin, escenario):
    cliente.patch(
        f"{API}/productos/{escenario['producto']['id']}", headers=admin, json={"tipo": "preparado"}
    )
    assert producir(cliente, admin, escenario["producto"]).json()["codigo"] == "PRODUCTO_NO_ES_LOTE"


def test_si_no_alcanza_un_insumo_no_se_mueve_nada(cliente, admin, escenario):
    r = producir(cliente, admin, escenario["producto"], cantidad="30")  # 1500 g de harina; hay 1400
    assert (r.status_code, r.json()["codigo"]) == (409, "STOCK_INSUFICIENTE")
    assert r.json()["detalle"]["nombre"] == "Harina prod"
    assert "Harina prod" in r.json()["mensaje"]
    # Nada quedó consumido: se puede producir lo que sí alcanza.
    assert producir(cliente, admin, escenario["producto"], cantidad="24").status_code == 201


def test_anular_devuelve_los_insumos_a_sus_lotes(cliente, admin, escenario, db):
    p = producir(cliente, admin, escenario["producto"]).json()
    r = cliente.post(
        f"{API}/producciones/{p['id']}/anular",
        headers=admin,
        json={"motivo": "Se registró dos veces"},
    )
    assert r.status_code == 200, r.json()
    assert r.json()["anulada"] is True
    # La harina vuelve completa: se puede producir otra vez con el mismo costo.
    otra = producir(cliente, admin, escenario["producto"]).json()
    assert otra["costo_total"] == 14500


def test_no_se_anula_si_ya_salio_parte_de_lo_producido(cliente, admin, escenario, db, ctx):
    p = producir(cliente, admin, escenario["producto"]).json()
    motor.consumir(
        db,
        ctx,
        tipo_item="producto",
        item_id=uuid.UUID(escenario["producto"]["id"]),
        cantidad=D("1"),
        tipo_mov="venta",
        referencia_tipo="venta",
        referencia_id=uuid.uuid4(),
    )
    db.commit()
    r = cliente.post(
        f"{API}/producciones/{p['id']}/anular", headers=admin, json={"motivo": "Error"}
    )
    assert r.json()["codigo"] == "PRODUCCION_CON_SALIDAS"


def test_cambiar_la_receta_no_altera_lo_ya_producido(cliente, admin, escenario):
    p = producir(cliente, admin, escenario["producto"], cantidad="6").json()
    cliente.put(
        f"{API}/productos/{escenario['producto']['id']}/receta",
        headers=admin,
        json={
            "rendimiento": "12",
            "items": [{"insumo_id": escenario["harina"]["id"], "cantidad": "1"}],
        },
    )
    despues = cliente.get(f"{API}/producciones/{p['id']}", headers=admin).json()
    assert (despues["receta_version"], despues["costo_total"]) == (1, 7200)


def test_produccion_registra_pero_solo_el_admin_anula(
    cliente, admin, escenario, crear_usuario, login
):
    produccion = login(crear_usuario("produccion"))
    p = producir(cliente, produccion, escenario["producto"])
    assert p.status_code == 201
    r = cliente.post(
        f"{API}/producciones/{p.json()['id']}/anular", headers=produccion, json={"motivo": "Error"}
    )
    assert r.status_code == 403
