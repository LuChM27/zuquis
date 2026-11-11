"""Carta (#16) y recetas con costeo teórico (#20)."""

import uuid
from decimal import Decimal as D

import pytest
from sqlalchemy import select

from app.core.deps import Contexto
from app.modules.auditoria.models import Auditoria
from app.modules.inventario import motor
from tests.conftest import SEDE_PRINCIPAL

API = "/api/v1"


@pytest.fixture
def categoria(cliente, admin) -> str:
    return next(
        c["id"]
        for c in cliente.get(f"{API}/categorias", headers=admin).json()
        if c["nombre"] == "Salado"
    )


def crear_producto(cliente, headers, categoria, **extra):
    datos = {
        "categoria_id": categoria,
        "nombre": f"Pastel {uuid.uuid4().hex[:5]}",
        "tipo": "lote",
        "precio": 4500,
    }
    r = cliente.post(f"{API}/productos", headers=headers, json=datos | extra)
    assert r.status_code == 201, r.json()
    return r.json()


def crear_insumo(cliente, headers, nombre, unidad):
    return cliente.post(
        f"{API}/insumos", headers=headers, json={"nombre": nombre, "unidad_base": unidad}
    ).json()


def comprar(db, ctx, insumo_id, cantidad, costo):
    motor.crear_lote(
        db,
        ctx,
        tipo_item="insumo",
        item_id=uuid.UUID(insumo_id),
        origen="compra",
        origen_id=None,
        cantidad=D(cantidad),
        costo_unitario=D(costo),
        tipo_mov="compra",
        referencia_tipo="compra",
        referencia_id=uuid.uuid4(),
    )


def test_categorias_iniciales_en_orden(cliente, admin):
    nombres = [c["nombre"] for c in cliente.get(f"{API}/categorias", headers=admin).json()]
    assert nombres[:3] == ["Panadería", "Salado", "Saludable"]
    assert nombres[-1] == "Adiciones"
    assert len(nombres) == 12


def test_cambio_de_precio_genera_historial_y_auditoria(cliente, admin, categoria, db):
    p = crear_producto(cliente, admin, categoria)
    r = cliente.patch(f"{API}/productos/{p['id']}", headers=admin, json={"precio": 5000})
    assert r.json()["precio"] == 5000
    historial = cliente.get(f"{API}/productos/{p['id']}/precios", headers=admin).json()
    assert [(h["precio_anterior"], h["precio_nuevo"]) for h in historial] == [
        (4500, 5000),
        (None, 4500),
    ]
    assert historial[0]["usuario"] == "Prueba"
    # Un cambio sin precio no agrega historial.
    cliente.patch(f"{API}/productos/{p['id']}", headers=admin, json={"disponible": False})
    assert len(cliente.get(f"{API}/productos/{p['id']}/precios", headers=admin).json()) == 2
    cambios = db.scalars(
        select(Auditoria).where(Auditoria.entidad == "productos", Auditoria.entidad_id == p["id"])
    ).all()
    assert any(
        a.antes and a.antes["precio"] == 4500 and a.despues["precio"] == 5000 for a in cambios
    )


def test_producto_desactivado_no_aparece_en_el_pos_pero_si_en_reportes(cliente, admin, categoria):
    p = crear_producto(cliente, admin, categoria)
    cliente.patch(f"{API}/productos/{p['id']}", headers=admin, json={"activo": False})
    pos = [x["id"] for x in cliente.get(f"{API}/productos", headers=admin).json()]
    todos = [
        x["id"]
        for x in cliente.get(f"{API}/productos?incluir_inactivos=true", headers=admin).json()
    ]
    assert p["id"] not in pos
    assert p["id"] in todos


def test_solo_carta_editar_cambia_precios(cliente, admin, categoria, crear_usuario, login):
    p = crear_producto(cliente, admin, categoria)
    produccion = login(crear_usuario("produccion"))
    cajero = login(crear_usuario("cajero"))
    for headers in (produccion, cajero):
        assert (
            cliente.patch(
                f"{API}/productos/{p['id']}", headers=headers, json={"precio": 1}
            ).status_code
            == 403
        )
    # El cajero ve la carta (la usa el POS).
    assert cliente.get(f"{API}/productos", headers=cajero).status_code == 200


def test_adiciones_se_asignan_a_productos(cliente, admin, categoria):
    queso = cliente.post(
        f"{API}/modificadores", headers=admin, json={"nombre": "Queso mozzarella", "precio": 2000}
    ).json()
    p = crear_producto(cliente, admin, categoria, modificador_ids=[queso["id"]])
    assert [m["nombre"] for m in p["modificadores"]] == ["Queso mozzarella"]
    r = cliente.patch(f"{API}/productos/{p['id']}", headers=admin, json={"modificador_ids": []})
    assert r.json()["modificadores"] == []


def test_costo_teorico_al_peso_contra_calculo_manual(cliente, admin, categoria, db, crear_usuario):
    ctx = Contexto(usuario_id=crear_usuario("admin").id, sede_id=SEDE_PRINCIPAL)
    harina = crear_insumo(cliente, admin, "Harina costeo", "g")
    mantequilla = crear_insumo(cliente, admin, "Mantequilla costeo", "g")
    huevos = crear_insumo(cliente, admin, "Huevos costeo", "und")
    comprar(db, ctx, harina["id"], "50000", "2.500000")  # compra vieja: no cuenta
    comprar(db, ctx, harina["id"], "50000", "3.000000")  # último costo de compra
    comprar(db, ctx, mantequilla["id"], "1000", "18.500000")
    comprar(db, ctx, huevos["id"], "30", "650.000000")
    db.commit()
    p = crear_producto(cliente, admin, categoria)
    r = cliente.put(
        f"{API}/productos/{p['id']}/receta",
        headers=admin,
        json={
            "rendimiento": "12",
            "items": [
                {"insumo_id": harina["id"], "cantidad": "600"},
                {"insumo_id": mantequilla["id"], "cantidad": "250"},
                {"insumo_id": huevos["id"], "cantidad": "3"},
            ],
        },
    )
    assert r.status_code == 200, r.json()
    costo = cliente.get(f"{API}/productos/{p['id']}/costo", headers=admin).json()
    assert [i["costo"] for i in costo["items"]] == [1800, 4625, 1950]
    assert costo["costo_receta"] == 8375
    assert costo["costo_unitario"] == "697.916667"
    assert costo["costo_por_unidad"] == 698
    assert (costo["margen"], costo["margen_porcentaje"]) == (3802, "84.4889")
    assert costo["completo"] is True


def test_costo_marca_incompleto_si_un_insumo_nunca_se_compro(cliente, admin, categoria):
    nuevo = crear_insumo(cliente, admin, "Insumo sin compras", "g")
    p = crear_producto(cliente, admin, categoria)
    cliente.put(
        f"{API}/productos/{p['id']}/receta",
        headers=admin,
        json={"rendimiento": "1", "items": [{"insumo_id": nuevo["id"], "cantidad": "10"}]},
    )
    costo = cliente.get(f"{API}/productos/{p['id']}/costo", headers=admin).json()
    assert costo["completo"] is False
    assert costo["items"][0]["costo"] is None


def test_editar_receta_crea_version_y_conserva_la_anterior(
    cliente, admin, categoria, crear_usuario, login
):
    harina = crear_insumo(cliente, admin, "Harina versiones", "g")
    p = crear_producto(cliente, admin, categoria)
    url = f"{API}/productos/{p['id']}/receta"
    produccion = login(crear_usuario("produccion"))  # Producción edita recetas, no precios
    v1 = cliente.put(
        url,
        headers=produccion,
        json={"rendimiento": "12", "items": [{"insumo_id": harina["id"], "cantidad": "600"}]},
    )
    assert v1.status_code == 200
    v2 = cliente.put(
        url,
        headers=produccion,
        json={"rendimiento": "10", "items": [{"insumo_id": harina["id"], "cantidad": "550"}]},
    )
    assert v2.json()["version"] == 2
    versiones = cliente.get(f"{url}/versiones", headers=admin).json()
    assert [(v["version"], v["vigente"], v["items"][0]["cantidad"]) for v in versiones] == [
        (2, True, "550.0000"),
        (1, False, "600.0000"),
    ]
    assert cliente.get(url, headers=admin).json()["version"] == 2


def test_receta_rechaza_insumo_repetido(cliente, admin, categoria):
    harina = crear_insumo(cliente, admin, "Harina repetida", "g")
    p = crear_producto(cliente, admin, categoria)
    r = cliente.put(
        f"{API}/productos/{p['id']}/receta",
        headers=admin,
        json={
            "rendimiento": "1",
            "items": [
                {"insumo_id": harina["id"], "cantidad": "1"},
                {"insumo_id": harina["id"], "cantidad": "2"},
            ],
        },
    )
    assert r.status_code == 422


def test_receta_de_una_adicion(cliente, admin):
    helado = crear_insumo(cliente, admin, "Helado de vainilla", "g")
    bola = cliente.post(
        f"{API}/modificadores", headers=admin, json={"nombre": "Bola de helado", "precio": 3000}
    ).json()
    r = cliente.put(
        f"{API}/modificadores/{bola['id']}/receta",
        headers=admin,
        json={"rendimiento": "1", "items": [{"insumo_id": helado["id"], "cantidad": "80"}]},
    )
    assert r.status_code == 200
    mods = cliente.get(f"{API}/modificadores", headers=admin).json()
    assert next(m for m in mods if m["id"] == bola["id"])["tiene_receta"] is True
