"""Escenario de ventas compartido (#29, #30, #31…): la carta del mockup del POS con recetas,
lotes y costos fáciles de seguir a mano, y ayudas para vender."""

import uuid
from decimal import Decimal as D

import pytest

from app.core.deps import Contexto
from app.modules.inventario import motor
from tests.conftest import SEDE_PRINCIPAL

API = "/api/v1"


@pytest.fixture
def ctx(crear_usuario) -> Contexto:
    return Contexto(usuario_id=crear_usuario("admin").id, sede_id=SEDE_PRINCIPAL)


@pytest.fixture
def metodos(cliente, admin) -> dict[str, str]:
    return {m["nombre"]: m["id"] for m in cliente.get(f"{API}/metodos-pago", headers=admin).json()}


def post(cliente, headers, ruta, json):
    r = cliente.post(f"{API}{ruta}", headers=headers, json=json)
    assert r.status_code in (200, 201), r.text
    return r.json()


def lote(db, ctx, tipo_item, item_id, cantidad, costo):
    motor.crear_lote(
        db,
        ctx,
        tipo_item=tipo_item,
        item_id=uuid.UUID(item_id),
        origen="compra" if tipo_item == "insumo" else "produccion",
        origen_id=None,
        cantidad=D(cantidad),
        costo_unitario=D(costo),
        tipo_mov="compra" if tipo_item == "insumo" else "entrada_produccion",
        referencia_tipo="prueba",
        referencia_id=uuid.uuid4(),
    )
    db.commit()


@pytest.fixture
def carta(cliente, admin, db, ctx):
    """El ejemplo del mockup del POS, con recetas y costos fáciles de seguir a mano.

    - Malteada de brownie $16.000 (preparada): 1 base de malteada a $3.000 + 300 ml de leche a $4.
    - Bola de helado $5.000 (adición): 80 g de helado a $20.
    - Soda frutos rojos $12.000 (preparada): 50 ml de jarabe a $30.
    - Pastel de pollo $4.500 (vitrina): 12 en un lote a $675.
    - Croissant de jamón y queso $7.500 (vitrina): 8 en un lote a $2.000.
    """
    cat = {c["nombre"]: c["id"] for c in cliente.get(f"{API}/categorias", headers=admin).json()}
    insumos = {}
    for nombre, unidad, cantidad, costo in (
        ("Base malteada venta", "und", "20", "3000"),
        ("Leche venta", "ml", "10000", "4"),
        ("Helado venta", "g", "5000", "20"),
        ("Jarabe venta", "ml", "2000", "30"),
    ):
        i = post(cliente, admin, "/insumos", {"nombre": nombre, "unidad_base": unidad})
        lote(db, ctx, "insumo", i["id"], cantidad, costo)
        insumos[nombre] = i["id"]

    helado = post(cliente, admin, "/modificadores", {"nombre": "Bola de helado", "precio": 5000})
    cliente.put(
        f"{API}/modificadores/{helado['id']}/receta",
        headers=admin,
        json={
            "rendimiento": "1",
            "items": [{"insumo_id": insumos["Helado venta"], "cantidad": "80"}],
        },
    )

    def producto(nombre, categoria, tipo, precio, **extra):
        return post(
            cliente,
            admin,
            "/productos",
            {"categoria_id": cat[categoria], "nombre": nombre, "tipo": tipo, "precio": precio}
            | extra,
        )

    malteada = producto(
        "Malteada de brownie", "Malteadas", "preparado", 16000, modificador_ids=[helado["id"]]
    )
    cliente.put(
        f"{API}/productos/{malteada['id']}/receta",
        headers=admin,
        json={
            "rendimiento": "1",
            "items": [
                {"insumo_id": insumos["Base malteada venta"], "cantidad": "1"},
                {"insumo_id": insumos["Leche venta"], "cantidad": "300"},
            ],
        },
    )
    soda = producto("Soda frutos rojos", "Sodas", "preparado", 12000)
    cliente.put(
        f"{API}/productos/{soda['id']}/receta",
        headers=admin,
        json={
            "rendimiento": "1",
            "items": [{"insumo_id": insumos["Jarabe venta"], "cantidad": "50"}],
        },
    )
    pastel = producto("Pastel de pollo", "Salado", "lote", 4500)
    lote(db, ctx, "producto", pastel["id"], "12", "675")
    croissant = producto("Croissant de jamón y queso", "Panadería", "lote", 7500)
    lote(db, ctx, "producto", croissant["id"], "8", "2000")
    return {
        "malteada": malteada,
        "helado": helado,
        "soda": soda,
        "pastel": pastel,
        "croissant": croissant,
        "insumos": insumos,
    }


@pytest.fixture
def caja_abierta(cliente, admin):
    r = cliente.post(f"{API}/caja/abrir", headers=admin, json={"base_inicial": 100000})
    assert r.status_code == 201, r.text


def venta_mockup(carta, metodos, **extra):
    return {
        "tipo_servicio": "local",
        "items": [
            {
                "producto_id": carta["malteada"]["id"],
                "cantidad": "1",
                "modificador_ids": [carta["helado"]["id"]],
            },
            {"producto_id": carta["soda"]["id"], "cantidad": "1", "nota": "Sin hielo"},
            {"producto_id": carta["pastel"]["id"], "cantidad": "2"},
            {"producto_id": carta["croissant"]["id"], "cantidad": "1", "nota": "Caliente"},
        ],
        "descuento": {"tipo": "valor", "valor": "3000", "motivo": "Cliente frecuente"},
        "propina": 2000,
        "pagos": [
            {"metodo_pago_id": metodos["Efectivo"], "monto": 28500},
            {"metodo_pago_id": metodos["Nequi"], "monto": 20000},
        ],
    } | extra


def vender(cliente, headers, datos, clave=None):
    return cliente.post(
        f"{API}/ventas",
        headers=headers | {"Idempotency-Key": clave or str(uuid.uuid4())},
        json=datos,
    )


def stock(db, tipo_item, item_id) -> D:
    return motor.stock(db, SEDE_PRINCIPAL, tipo_item, uuid.UUID(item_id))


def esperado(cliente, headers) -> dict[str, int]:
    actual = cliente.get(f"{API}/caja/actual", headers=headers).json()
    return {e["metodo"]: e["esperado"] for e in actual["esperado"]}
