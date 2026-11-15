"""Caso de control de la Fase 2 (#38): un día completo de ventas, gastos, una anulación y el
cierre con diferencia. Los valores esperados vienen de tests/control/fase2.md, calculados a
mano; esta prueba los reproduce por la API al peso.
"""

import uuid

import pytest

from tests.conftest import CLAVE, rol_base

API = "/api/v1"

# (venta, [(producto, cantidad, adiciones)], descuento, propina, pagos {método: (monto, recibido)})
VENTAS = [
    ("V1", [("cafe", 2)], None, 0, {"Efectivo": (6000, 10000)}),
    ("V2", [("capuchino", 1), ("pastel", 1)], None, 0, {"Nequi": 10500}),
    ("V3", [("malteada", 1, ["helado"])], None, 2000, {"Efectivo": 23000}),
    ("V4", [("pastel", 3)], None, 0, {"Bre-B": 13500}),
    ("V5", [("capuchino", 2)], None, 0, {"Efectivo": 7000, "Nequi": 5000}),
    ("V6", [("malteada", 1)], None, 0, {"Bancolombia": 16000}),
    ("V7", [("cafe", 1)], None, 0, {"Efectivo": 3000}),
    ("V8", [("pastel", 4)], None, 0, {"Efectivo": 10000, "Bre-B": 8000}),
    ("V9", [("capuchino", 1)], None, 1000, {"Nequi": 7000}),
    ("V10", [("malteada", 2)], ("porcentaje", "25", "Cliente frecuente"), 0, {"Efectivo": 24000}),
    ("V11", [("cafe", 1), ("pastel", 1)], None, 0, {"Efectivo": 7500}),
    ("V12", [("pastel", 1)], ("porcentaje", "100", "Cortesía de cumpleaños"), 0, {}),
    ("V13", [("capuchino", 2)], None, 0, {"Nequi": 12000}),
    ("V14", [("cafe", 3)], None, 0, {"Efectivo": 9000}),
    ("V15", [("malteada", 1)], None, 0, {"Nequi": 10000, "Efectivo": 6000}),
    ("V16", [("pastel", 2)], None, 0, {"Bancolombia": 9000}),
    ("V17", [("capuchino", 1), ("cafe", 1)], None, 1000, {"Efectivo": 10000}),
    ("V18", [("pastel", 2)], None, 0, {"Bre-B": 9000}),
    ("V19", [("malteada", 1)], None, 0, {"Efectivo": 16000}),
    ("V20", [("cafe", 1)], None, 0, {"Nequi": 3000}),
]

COSTOS = {  # costo de cada venta, de la tabla del caso
    "V1": 800, "V2": 1100, "V3": 900, "V4": 750, "V5": 1700, "V6": 900, "V7": 400,
    "V8": 1000, "V9": 850, "V10": 1800, "V11": 650, "V12": 250, "V13": 1750, "V14": 1200,
    "V15": 1050, "V16": 500, "V17": 1325, "V18": 600, "V19": 1050, "V20": 400,
}  # fmt: skip


@pytest.fixture
def dia(cliente, admin, db, crear_usuario, login):
    """Ejecuta el día completo (sin cerrar la caja) y devuelve lo necesario para revisarlo."""

    def enviar(headers, ruta, json, metodo="post", clave=None):
        extra = {"Idempotency-Key": clave} if clave else {}
        r = getattr(cliente, metodo)(f"{API}{ruta}", headers=headers | extra, json=json)
        assert r.status_code in (200, 201, 204), r.text
        return r.json() if r.status_code != 204 else None

    def post(ruta, json, metodo="post"):
        return enviar(admin, ruta, json, metodo)

    cat = {c["nombre"]: c["id"] for c in cliente.get(f"{API}/categorias", headers=admin).json()}
    metodos = {
        m["nombre"]: m["id"] for m in cliente.get(f"{API}/metodos-pago", headers=admin).json()
    }

    insumos = {
        clave: post("/insumos", {"nombre": nombre, "unidad_base": unidad})
        for clave, nombre, unidad in (
            ("cafe", "Café molido control", "g"),
            ("leche", "Leche control", "ml"),
            ("masa", "Masa de pastel control", "g"),
        )
    }
    compras = {}
    for nombre, clave, cantidad, costo in (
        ("cafe-C1", "cafe", "500", 20000),
        ("leche-C1", "leche", "2000", 6000),
        ("leche-C2", "leche", "4000", 14000),
        ("masa-C1", "masa", "600", 3000),
        ("masa-C2", "masa", "600", 3600),
    ):
        c = post(
            "/compras",
            {
                "estado_pago": "por_pagar",
                "items": [
                    {"insumo_id": insumos[clave]["id"], "cantidad": cantidad, "costo_total": costo}
                ],
            },
        )
        compras[nombre] = c["items"][0]["lote_id"]

    helado = post("/modificadores", {"nombre": "Bola de helado control", "precio": 5000})

    def producto(nombre, categoria, tipo, precio, receta, rendimiento="1", **extra):
        p = post(
            "/productos",
            {"categoria_id": cat[categoria], "nombre": nombre, "tipo": tipo, "precio": precio}
            | extra,
        )
        items = [{"insumo_id": insumos[i]["id"], "cantidad": c} for i, c in receta]
        post(
            f"/productos/{p['id']}/receta",
            {"rendimiento": rendimiento, "items": items},
            metodo="put",
        )
        return p

    carta = {
        "cafe": producto("Café americano control", "Bebidas calientes", "preparado", 3000,
                         [("cafe", "10")]),
        "capuchino": producto("Capuchino control", "Bebidas calientes", "preparado", 6000,
                              [("cafe", "10"), ("leche", "150")]),
        "malteada": producto("Malteada control", "Malteadas", "preparado", 16000,
                             [("leche", "300")], modificador_ids=[helado["id"]]),
        "pastel": producto("Pastel de pollo control", "Salado", "lote", 4500,
                           [("masa", "600")], rendimiento="12"),
    }  # fmt: skip
    p1 = post("/producciones", {"producto_id": carta["pastel"]["id"], "cantidad_producida": "12"})
    p2 = post("/producciones", {"producto_id": carta["pastel"]["id"], "cantidad_producida": "12"})

    # El cajero tiene tope del 10 %; el jefe autoriza con su PIN.
    jefe = crear_usuario("admin", nombre="Jefe control")
    enviar(login(jefe), "/auth/pin", {"clave_actual": CLAVE, "pin": "9090"}, metodo="put")
    cliente.patch(
        f"{API}/configuracion",
        headers=admin,
        json={"tope_descuento_por_rol": {str(rol_base(db, "cajero").id): "10"}},
    )
    cajero = login(crear_usuario("cajero", nombre="Cajero control"))

    post("/caja/abrir", {"base_inicial": 100000})

    ventas = {}
    for numero, lineas, descuento, propina, pagos in VENTAS:
        cuerpo = {
            "tipo_servicio": "local",
            "items": [
                {
                    "producto_id": carta[linea[0]]["id"],
                    "cantidad": str(linea[1]),
                    "modificador_ids": [helado["id"]] if len(linea) > 2 else [],
                }
                for linea in lineas
            ],
            "propina": propina,
            "pagos": [
                {
                    "metodo_pago_id": metodos[m],
                    "monto": v[0] if isinstance(v, tuple) else v,
                    "recibido": v[1] if isinstance(v, tuple) else None,
                }
                for m, v in pagos.items()
            ],
        }
        if descuento:
            tipo, valor, motivo = descuento
            cuerpo["descuento"] = {"tipo": tipo, "valor": valor, "motivo": motivo}
        quien = admin
        if numero == "V10":
            quien = cajero
            cuerpo["autorizacion"] = {"usuario_id": str(jefe.id), "pin": "9090"}
        ventas[numero] = enviar(quien, "/ventas", cuerpo, clave=str(uuid.uuid4()))

    categorias_gasto = {
        c["nombre"]: c["id"] for c in cliente.get(f"{API}/categorias-gasto", headers=admin).json()
    }
    for categoria, descripcion, monto in (
        ("Papelería", "Resma de papel", 8000),
        ("Servicios públicos (agua, energía, gas)", "Recibo de energía", 25000),
    ):
        post(
            "/gastos",
            {
                "categoria_id": categorias_gasto[categoria],
                "descripcion": descripcion,
                "monto": monto,
                "metodo_pago_id": metodos["Efectivo"],
                "fuente": "caja",
            },
        )

    anulada = post(f"/ventas/{ventas['V18']['id']}/anular", {"motivo": "Se cobró dos veces"})
    return {
        "ventas": ventas,
        "anulada": anulada,
        "metodos": metodos,
        "insumos": insumos,
        "carta": carta,
        "lotes": compras | {"P1": p1["lote_resultante_id"], "P2": p2["lote_resultante_id"]},
        "jefe": jefe,
    }


def test_cada_venta_da_su_total_y_su_costo(dia):
    v = dia["ventas"]
    assert {n: v[n]["total"] for n in v} == {
        n: t
        for n, t in zip(
            v,
            [6000, 10500, 21000, 13500, 12000, 16000, 3000, 18000, 6000, 24000,
             7500, 0, 12000, 9000, 16000, 9000, 9000, 9000, 16000, 3000],
            strict=True,
        )
    }  # fmt: skip
    assert {n: v[n]["costo_total"] for n in v} == COSTOS
    assert v["V1"]["cambio"] == 4000
    assert v["V10"]["descuento_total"] == 8000
    assert v["V10"]["descuento_autorizado_por"] == str(dia["jefe"].id)
    assert v["V12"]["cortesia"] is True and v["V12"]["pagos"] == []
    # V13: 200 ml de leche a $3 (se acaba C1) + 100 ml a $3,5 + 20 g de café a $40.
    assert v["V13"]["costo_total"] == 600 + 350 + 800


def test_ventas_del_dia_y_costo_de_ventas(cliente, admin, dia):
    sesion = dia["ventas"]["V1"]["caja_sesion_id"]
    r = cliente.get(f"{API}/ventas", headers=admin, params={"caja_sesion_id": sesion, "size": 100})
    assert r.status_code == 200, r.text
    pagadas = [x for x in r.json()["items"] if x["estado"] == "pagada"]
    assert len(pagadas) == 19
    assert sum(x["total"] for x in pagadas) == 211500
    assert sum(x["descuento_total"] for x in pagadas) == 12500
    assert sum(x["propina"] for x in pagadas) == 4000
    assert sum(x["costo_total"] for x in pagadas) == 18375
    assert dia["anulada"]["estado"] == "anulada"


def test_cierre_cuadra_por_metodo_con_diferencia_en_efectivo(cliente, admin, dia):
    m = dia["metodos"]
    r = cliente.get(f"{API}/caja/actual/cierre", headers=admin)
    assert r.status_code == 200, r.text
    vista = r.json()
    esperado = {a["metodo"]: a["esperado"] for a in vista["arqueo"] if a["esperado"]}
    assert esperado == {"Efectivo": 188500, "Nequi": 47500, "Bre-B": 21500, "Bancolombia": 25000}
    assert vista["efectivo_esperado"] == 188500
    assert {linea["concepto"]: linea["monto"] for linea in vista["efectivo"]} == {
        "Base inicial": 100000,
        "Ventas en efectivo": 118500,
        "Propinas en efectivo": 3000,
        "Gastos pagados de la caja": -33000,
    }
    assert vista["resumen"] == {
        "ventas": 220500,
        "abonos": 0,
        "propinas": 4000,
        "gastos": 33000,
        "domicilios_entregados": 0,
        "pagos_proveedores": 0,
        "anulaciones": 9000,
    }

    contado = {"Efectivo": 188000, "Nequi": 47500, "Bre-B": 21500, "Bancolombia": 25000}
    cuerpo = {"contado": [{"metodo_pago_id": m[n], "contado": v} for n, v in contado.items()]}
    r = cliente.post(f"{API}/caja/cerrar", headers=admin, json=cuerpo)
    assert (r.status_code, r.json()["codigo"]) == (422, "OBSERVACION_REQUERIDA")

    cuerpo["observacion"] = "Faltan $500 en efectivo, posiblemente cambio mal entregado."
    r = cliente.post(f"{API}/caja/cerrar", headers=admin, json=cuerpo)
    assert r.status_code == 200, r.text
    cierre = r.json()
    assert cierre["diferencia_total"] == -500
    assert {a["metodo"]: a["diferencia"] for a in cierre["arqueos"] if a["esperado"]} == {
        "Efectivo": -500,
        "Nequi": 0,
        "Bre-B": 0,
        "Bancolombia": 0,
    }


def test_stock_final_por_lote(cliente, admin, dia):
    lotes, insumos, carta = dia["lotes"], dia["insumos"], dia["carta"]

    def con_existencia(ruta):
        r = cliente.get(f"{API}{ruta}", headers=admin)
        assert r.status_code == 200, r.text
        return [(x["id"], x["cantidad_disponible"], x["costo_unitario"]) for x in r.json()]

    assert con_existencia(f"/insumos/{insumos['cafe']['id']}/lotes") == [
        (lotes["cafe-C1"], "340.0000", "40.000000")
    ]
    assert con_existencia(f"/insumos/{insumos['leche']['id']}/lotes") == [
        (lotes["leche-C2"], "3150.0000", "3.500000")
    ]
    assert con_existencia(f"/insumos/{insumos['masa']['id']}/lotes") == []
    # P1 se agotó; la anulación devolvió los 2 pasteles de la V18 a P2.
    assert con_existencia(f"/productos/{carta['pastel']['id']}/lotes") == [
        (lotes["P2"], "12.0000", "300.000000")
    ]

    r = cliente.get(f"{API}/inventario/stock", headers=admin)
    ids = {i["id"] for i in insumos.values()} | {carta["pastel"]["id"]}
    valor = {s["nombre"]: s["valor"] for s in r.json() if s["item_id"] in ids}
    assert valor == {
        "Café molido control": 13600,
        "Leche control": 11025,
        "Masa de pastel control": 0,
        "Pastel de pollo control": 3600,
    }
    assert sum(valor.values()) == 28225 == 46600 - 18375
