"""Caso de control de la Fase 1 (#27): una semana de compras a precios distintos, dos
producciones, una merma y un ajuste. Los valores esperados vienen de tests/control/fase1.md,
calculados a mano; esta prueba los reproduce por la API al peso.
"""

from datetime import timedelta

import pytest

from app.shared.fechas import hoy

API = "/api/v1"

COMPRAS = [  # (día, {insumo: (presentaciones, costo de la línea)})
    (1, {"harina": ("1", 3000), "mantequilla": ("1", 9000), "huevos": ("1", 13500)}),
    (3, {"harina": ("1", 3400), "mantequilla": ("1", 9500), "huevos": ("1", 14100)}),
    (5, {"harina": ("2", 7000), "mantequilla": ("1", 10000), "huevos": ("1", 15000)}),
]


@pytest.fixture
def semana(cliente, admin):
    """Ejecuta la semana completa y devuelve lo necesario para revisar el resultado."""

    def post(ruta, json):
        r = cliente.post(f"{API}{ruta}", headers=admin, json=json)
        assert r.status_code in (200, 201), r.text
        return r.json()

    insumos = {
        clave: post(
            "/insumos",
            {
                "nombre": nombre,
                "unidad_base": unidad,
                "presentaciones": [{"nombre": presentacion, "factor": factor}],
            },
        )
        for clave, nombre, unidad, presentacion, factor in (
            ("harina", "Harina de trigo control", "g", "Bolsa 1 kg", "1000"),
            ("mantequilla", "Mantequilla control", "g", "Barra 500 g", "500"),
            ("huevos", "Huevos control", "und", "Panal 30", "30"),
        )
    }
    salado = next(
        c["id"]
        for c in cliente.get(f"{API}/categorias", headers=admin).json()
        if c["nombre"] == "Salado"
    )
    pastel = post(
        "/productos",
        {
            "categoria_id": salado,
            "nombre": "Pastel de pollo control",
            "tipo": "lote",
            "precio": 4500,
        },
    )
    r = cliente.put(
        f"{API}/productos/{pastel['id']}/receta",
        headers=admin,
        json={
            "rendimiento": "12",
            "items": [
                {"insumo_id": insumos["harina"]["id"], "cantidad": "600"},
                {"insumo_id": insumos["mantequilla"]["id"], "cantidad": "250"},
                {"insumo_id": insumos["huevos"]["id"], "cantidad": "4"},
            ],
        },
    )
    assert r.status_code == 200, r.text

    inicio = hoy() - timedelta(days=7)
    compras = []
    for dia, lineas in COMPRAS:
        compras.append(
            post(
                "/compras",
                {
                    "fecha": (inicio + timedelta(days=dia)).isoformat(),
                    "estado_pago": "por_pagar",
                    "items": [
                        {
                            "insumo_id": insumos[clave]["id"],
                            "presentacion_id": insumos[clave]["presentaciones"][0]["id"],
                            "cantidad": cantidad,
                            "costo_total": costo,
                        }
                        for clave, (cantidad, costo) in lineas.items()
                    ],
                },
            )
        )
    produccion1 = post("/producciones", {"producto_id": pastel["id"], "cantidad_producida": "12"})
    merma = post(
        "/mermas",
        {
            "tipo_item": "insumo",
            "item_id": insumos["mantequilla"]["id"],
            "cantidad": "200",
            "motivo": "danado",
        },
    )
    produccion2 = post("/producciones", {"producto_id": pastel["id"], "cantidad_producida": "18"})
    ajuste = post(
        "/ajustes",
        {
            "tipo_item": "insumo",
            "item_id": insumos["harina"]["id"],
            "cantidad_contada": "2550",
            "motivo": "Conteo del día 7",
        },
    )

    def lote_de(compra, clave):
        return next(i["lote_id"] for i in compra["items"] if i["insumo_id"] == insumos[clave]["id"])

    lotes = {
        f"{clave}-C{n}": lote_de(compra, clave)
        for n, compra in enumerate(compras, start=1)
        for clave in insumos
    }
    lotes["P1"] = produccion1["lote_resultante_id"]
    lotes["P2"] = produccion2["lote_resultante_id"]
    return {
        "insumos": insumos,
        "pastel": pastel,
        "compras": compras,
        "produccion1": produccion1,
        "produccion2": produccion2,
        "merma": merma,
        "ajuste": ajuste,
        "lotes": lotes,
    }


def consumos(produccion) -> dict[str, tuple[str, int]]:
    return {c["insumo"]: (c["cantidad"], c["costo_total"]) for c in produccion["consumos"]}


def test_costo_unitario_de_cada_lote_comprado(semana):
    unitarios = [
        sorted((i["insumo"], i["costo_unitario"]) for i in compra["items"])
        for compra in semana["compras"]
    ]
    assert unitarios == [
        [
            ("Harina de trigo control", "3.000000"),
            ("Huevos control", "450.000000"),
            ("Mantequilla control", "18.000000"),
        ],
        [
            ("Harina de trigo control", "3.400000"),
            ("Huevos control", "470.000000"),
            ("Mantequilla control", "19.000000"),
        ],
        [
            ("Harina de trigo control", "3.500000"),
            ("Huevos control", "500.000000"),
            ("Mantequilla control", "20.000000"),
        ],
    ]


def test_produccion_1_consume_del_primer_lote(semana):
    p = semana["produccion1"]
    assert consumos(p) == {
        "Harina de trigo control": ("600.0000", 1800),
        "Mantequilla control": ("250.0000", 4500),
        "Huevos control": ("4.0000", 1800),
    }
    assert (p["costo_total"], p["costo_unitario"]) == (8100, "675.000000")


def test_merma_sale_del_primer_lote(semana):
    assert semana["merma"]["costo_total"] == 3600


def test_produccion_2_cruza_lotes(semana):
    p = semana["produccion2"]
    assert consumos(p) == {
        "Harina de trigo control": ("900.0000", 2900),
        "Mantequilla control": ("375.0000", 7075),
        "Huevos control": ("6.0000", 2700),
    }
    assert (p["costo_total"], p["costo_unitario"]) == (12675, "704.166667")


def test_ajuste_positivo_al_costo_del_ultimo_lote(semana):
    a = semana["ajuste"]
    assert (a["cantidad_sistema"], a["diferencia"], a["costo_total"]) == (
        "2500.0000",
        "50.0000",
        175,
    )


def test_lotes_resultantes(cliente, admin, semana):
    lotes = semana["lotes"]

    def con_existencia(ruta):
        r = cliente.get(f"{API}{ruta}", headers=admin)
        assert r.status_code == 200, r.text
        return [(x["id"], x["cantidad_disponible"], x["costo_unitario"]) for x in r.json()]

    insumos = semana["insumos"]
    harina = con_existencia(f"/insumos/{insumos['harina']['id']}/lotes")
    assert harina[:2] == [
        (lotes["harina-C2"], "500.0000", "3.400000"),
        (lotes["harina-C3"], "2000.0000", "3.500000"),
    ]
    assert harina[2][1:] == ("50.0000", "3.500000")  # el lote del ajuste
    assert len(harina) == 3
    assert con_existencia(f"/insumos/{insumos['mantequilla']['id']}/lotes") == [
        (lotes["mantequilla-C2"], "175.0000", "19.000000"),
        (lotes["mantequilla-C3"], "500.0000", "20.000000"),
    ]
    assert con_existencia(f"/insumos/{insumos['huevos']['id']}/lotes") == [
        (lotes["huevos-C1"], "20.0000", "450.000000"),
        (lotes["huevos-C2"], "30.0000", "470.000000"),
        (lotes["huevos-C3"], "30.0000", "500.000000"),
    ]
    assert con_existencia(f"/productos/{semana['pastel']['id']}/lotes") == [
        (lotes["P1"], "12.0000", "675.000000"),
        (lotes["P2"], "18.0000", "704.166667"),
    ]


def test_stock_y_valor_del_inventario(cliente, admin, semana):
    r = cliente.get(f"{API}/inventario/stock", headers=admin)
    assert r.status_code == 200, r.text
    ids = {i["id"] for i in semana["insumos"].values()} | {semana["pastel"]["id"]}
    stock = {s["nombre"]: (s["cantidad"], s["valor"]) for s in r.json() if s["item_id"] in ids}
    assert stock == {
        "Harina de trigo control": ("2550.0000", 8875),
        "Mantequilla control": ("675.0000", 13325),
        "Huevos control": ("80.0000", 38100),
        "Pastel de pollo control": ("30.0000", 20775),
    }
    assert sum(valor for _, valor in stock.values()) == 81075 == 84500 - 3600 + 175


def test_kardex_de_la_mantequilla(cliente, admin, semana):
    lotes = semana["lotes"]
    r = cliente.get(f"{API}/insumos/{semana['insumos']['mantequilla']['id']}/kardex", headers=admin)
    assert r.status_code == 200, r.text
    filas = [
        (
            f["tipo"],
            f["lote_id"],
            f["cantidad"],
            f["costo_total"],
            f["saldo_cantidad"],
            f["saldo_costo"],
        )
        for f in r.json()["items"]
    ]
    c1, c2, c3 = lotes["mantequilla-C1"], lotes["mantequilla-C2"], lotes["mantequilla-C3"]
    assert filas == [
        ("compra", c1, "500.0000", 9000, "500.0000", 9000),
        ("compra", c2, "500.0000", 9500, "1000.0000", 18500),
        ("compra", c3, "500.0000", 10000, "1500.0000", 28500),
        ("consumo_produccion", c1, "-250.0000", -4500, "1250.0000", 24000),
        ("merma", c1, "-200.0000", -3600, "1050.0000", 20400),
        ("consumo_produccion", c1, "-50.0000", -900, "1000.0000", 19500),
        ("consumo_produccion", c2, "-325.0000", -6175, "675.0000", 13325),
    ]
