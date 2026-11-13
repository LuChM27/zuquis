"""Stock, lotes, kardex, alertas, resumen y verificación nocturna (#23)."""

import uuid
from datetime import time, timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import select, text

from app.core.deps import Contexto
from app.modules.inventario import motor, tareas
from app.modules.inventario.models import VerificacionInventario
from app.shared.fechas import hoy
from tests.conftest import SEDE_PRINCIPAL

API = "/api/v1"


@pytest.fixture
def ctx(crear_usuario) -> Contexto:
    return Contexto(usuario_id=crear_usuario("admin").id, sede_id=SEDE_PRINCIPAL)


def insumo(cliente, admin, nombre: str, minimo="0", **extra) -> dict:
    return cliente.post(
        f"{API}/insumos",
        headers=admin,
        json={"nombre": nombre, "unidad_base": "g", "stock_minimo": minimo} | extra,
    ).json()


def lote(db, ctx, item, cantidad: str, costo: str, vence=None, tipo_item="insumo"):
    nuevo = motor.crear_lote(
        db,
        ctx,
        tipo_item=tipo_item,
        item_id=uuid.UUID(item["id"]),
        origen="compra" if tipo_item == "insumo" else "produccion",
        origen_id=None,
        cantidad=D(cantidad),
        costo_unitario=D(costo),
        tipo_mov="compra" if tipo_item == "insumo" else "entrada_produccion",
        referencia_tipo="compra" if tipo_item == "insumo" else "produccion",
        referencia_id=uuid.uuid4(),
        vence=vence,
    )
    db.commit()
    return nuevo


def stock_de(cliente, headers, item, tipo_item="insumo") -> dict:
    r = cliente.get(f"{API}/inventario/stock", headers=headers, params={"tipo_item": tipo_item})
    assert r.status_code == 200, r.text
    return next(s for s in r.json() if s["item_id"] == item["id"])


def categoria(cliente, admin, nombre="Salado") -> str:
    return next(
        c["id"]
        for c in cliente.get(f"{API}/categorias", headers=admin).json()
        if c["nombre"] == nombre
    )


# --- Stock ----------------------------------------------------------------------------------


def test_stock_bien_con_valor_a_costo_de_lote(cliente, admin, db, ctx):
    harina = insumo(cliente, admin, "Harina stock", minimo="500")
    lote(db, ctx, harina, "1000", "3")
    lote(db, ctx, harina, "2000", "4", vence=hoy() + timedelta(days=60))
    s = stock_de(cliente, admin, harina)
    assert s["cantidad"] == "3000.0000"
    assert s["cantidad_vencida"] == "0.0000"
    assert s["minimo"] == "500.0000"
    assert s["unidad"] == "g"
    assert s["estado"] == "bien"
    assert s["valor"] == 11000
    assert s["lotes"] == 2
    assert s["proximo_vencimiento"] == (hoy() + timedelta(days=60)).isoformat()


def test_stock_bajo_el_minimo(cliente, admin, db, ctx):
    leche = insumo(cliente, admin, "Leche stock", minimo="6000")
    lote(db, ctx, leche, "2000", "4")
    assert stock_de(cliente, admin, leche)["estado"] == "bajo_minimo"


def test_stock_por_vencer_usa_los_dias_generales(cliente, admin, db, ctx):
    fresas = insumo(cliente, admin, "Fresas stock", minimo="500")
    lote(db, ctx, fresas, "800", "20", vence=hoy() + timedelta(days=1))
    assert stock_de(cliente, admin, fresas)["estado"] == "por_vencer"


def test_stock_por_vencer_respeta_los_dias_del_insumo(cliente, admin, db, ctx):
    queso = insumo(cliente, admin, "Queso stock", dias_alerta_vencimiento=10)
    lote(db, ctx, queso, "800", "20", vence=hoy() + timedelta(days=8))
    assert stock_de(cliente, admin, queso)["estado"] == "por_vencer"
    crema = insumo(cliente, admin, "Crema stock", dias_alerta_vencimiento=1)
    lote(db, ctx, crema, "800", "20", vence=hoy() + timedelta(days=2))
    assert stock_de(cliente, admin, crema)["estado"] == "bien"


def test_stock_separa_lo_vencido(cliente, admin, db, ctx):
    crema = insumo(cliente, admin, "Crema vencida stock")
    lote(db, ctx, crema, "300", "10", vence=hoy() - timedelta(days=1))
    lote(db, ctx, crema, "700", "10", vence=hoy() + timedelta(days=30))
    s = stock_de(cliente, admin, crema)
    assert (s["cantidad"], s["cantidad_vencida"]) == ("700.0000", "300.0000")
    assert s["estado"] == "vencido"
    # El próximo vencimiento es el de lo vigente; lo vencido ya pasó.
    assert s["proximo_vencimiento"] == (hoy() + timedelta(days=30)).isoformat()


def test_stock_sin_lotes_aparece_en_cero(cliente, admin):
    cafe = insumo(cliente, admin, "Café stock", minimo="100")
    s = stock_de(cliente, admin, cafe)
    assert (s["cantidad"], s["lotes"], s["estado"]) == ("0.0000", 0, "bajo_minimo")


def test_stock_cuenta_las_recetas_vigentes_que_usan_el_insumo(cliente, admin):
    azucar = insumo(cliente, admin, "Azúcar recetas")
    salado = categoria(cliente, admin)
    for nombre in ("Brownie recetas", "Torta recetas"):
        producto = cliente.post(
            f"{API}/productos",
            headers=admin,
            json={"categoria_id": salado, "nombre": nombre, "tipo": "lote", "precio": 1000},
        ).json()
        for _ in range(2):  # dos versiones: solo cuenta la vigente
            cliente.put(
                f"{API}/productos/{producto['id']}/receta",
                headers=admin,
                json={"rendimiento": "1", "items": [{"insumo_id": azucar["id"], "cantidad": "10"}]},
            )
    assert stock_de(cliente, admin, azucar)["usado_en_recetas"] == 2


def test_stock_incluye_productos_en_vitrina(cliente, admin, db, ctx):
    producto = cliente.post(
        f"{API}/productos",
        headers=admin,
        json={
            "categoria_id": categoria(cliente, admin),
            "nombre": "Croissant vitrina",
            "tipo": "lote",
            "precio": 3000,
        },
    ).json()
    lote(db, ctx, producto, "12", "900", tipo_item="producto")
    s = stock_de(cliente, admin, producto, tipo_item="producto")
    assert (s["nombre"], s["unidad"], s["cantidad"], s["valor"]) == (
        "Croissant vitrina",
        "und",
        "12.0000",
        10800,
    )


# --- Lotes ----------------------------------------------------------------------------------


def test_lotes_en_orden_peps_con_el_que_se_usa_primero(cliente, admin, db, ctx):
    harina = insumo(cliente, admin, "Harina lotes")
    vencido = lote(db, ctx, harina, "100", "2", vence=hoy() - timedelta(days=1))
    primero = lote(db, ctx, harina, "1000", "3")
    segundo = lote(db, ctx, harina, "1000", "4")
    agotado = lote(db, ctx, harina, "50", "5")
    motor.consumir(
        db,
        ctx,
        tipo_item="insumo",
        item_id=agotado.item_id,
        cantidad=D("50"),
        tipo_mov="merma",
        referencia_tipo="merma",
        referencia_id=uuid.uuid4(),
        lote_id=agotado.id,
    )
    db.commit()
    r = cliente.get(f"{API}/insumos/{harina['id']}/lotes", headers=admin)
    assert r.status_code == 200, r.text
    lotes = r.json()
    assert [x["id"] for x in lotes] == [str(vencido.id), str(primero.id), str(segundo.id)]
    assert [x["vencido"] for x in lotes] == [True, False, False]
    assert [x["se_usa_primero"] for x in lotes] == [False, True, False]


def test_lotes_de_un_insumo_que_no_existe(cliente, admin):
    r = cliente.get(f"{API}/insumos/{uuid.uuid4()}/lotes", headers=admin)
    assert r.status_code == 404


# --- Kardex ---------------------------------------------------------------------------------


def test_kardex_reproduce_cada_movimiento_con_su_saldo(cliente, admin, db, ctx):
    """Mantequilla: dos compras, una merma que cruza lotes y un ajuste positivo."""
    mantequilla = insumo(cliente, admin, "Mantequilla kardex")
    a = lote(db, ctx, mantequilla, "1000", "20")
    b = lote(db, ctx, mantequilla, "500", "24")
    cliente.post(
        f"{API}/mermas",
        headers=admin,
        json={
            "tipo_item": "insumo",
            "item_id": mantequilla["id"],
            "cantidad": "1200",
            "motivo": "danado",
        },
    )
    cliente.post(
        f"{API}/ajustes",
        headers=admin,
        json={
            "tipo_item": "insumo",
            "item_id": mantequilla["id"],
            "cantidad_contada": "350",
            "motivo": "Conteo semanal",
        },
    )
    r = cliente.get(f"{API}/insumos/{mantequilla['id']}/kardex", headers=admin)
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
    ajuste_lote = r.json()["items"][-1]["lote_id"]
    assert filas == [
        ("compra", str(a.id), "1000.0000", 20000, "1000.0000", 20000),
        ("compra", str(b.id), "500.0000", 12000, "1500.0000", 32000),
        ("merma", str(a.id), "-1000.0000", -20000, "500.0000", 12000),
        ("merma", str(b.id), "-200.0000", -4800, "300.0000", 7200),
        ("ajuste", ajuste_lote, "50.0000", 1200, "350.0000", 8400),
    ]
    assert r.json()["items"][2]["usuario"]


def test_movimientos_filtra_por_tipo_y_trae_el_nombre(cliente, admin, db, ctx):
    canela = insumo(cliente, admin, "Canela movimientos")
    lote(db, ctx, canela, "100", "50")
    cliente.post(
        f"{API}/mermas",
        headers=admin,
        json={"tipo_item": "insumo", "item_id": canela["id"], "cantidad": "10", "motivo": "danado"},
    )
    r = cliente.get(
        f"{API}/inventario/movimientos",
        headers=admin,
        params={"item_id": canela["id"], "tipo": "merma"},
    )
    assert r.status_code == 200, r.text
    (mov,) = r.json()["items"]
    assert (mov["item_nombre"], mov["cantidad"], mov["saldo_cantidad"]) == (
        "Canela movimientos",
        "-10.0000",
        "90.0000",
    )


# --- Alertas y resumen ----------------------------------------------------------------------


def alertas(cliente, headers) -> list[dict]:
    r = cliente.get(f"{API}/inventario/alertas", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_alertas_de_minimo_vencimiento_y_vencidos(cliente, admin, db, ctx):
    leche = insumo(cliente, admin, "Leche alerta", minimo="6000")
    lote(db, ctx, leche, "2000", "4")
    fresas = insumo(cliente, admin, "Fresas alerta")
    por_vencer = lote(db, ctx, fresas, "800", "20", vence=hoy() + timedelta(days=1))
    queso = insumo(cliente, admin, "Queso alerta")
    vencido = lote(db, ctx, queso, "300", "20", vence=hoy() - timedelta(days=1))
    todas = alertas(cliente, admin)
    assert ("bajo_minimo", leche["id"], None) in {
        (a["tipo"], a["item_id"], a["lote_id"]) for a in todas
    }
    assert ("por_vencer", fresas["id"], str(por_vencer.id)) in {
        (a["tipo"], a["item_id"], a["lote_id"]) for a in todas
    }
    assert ("vencido", queso["id"], str(vencido.id)) in {
        (a["tipo"], a["item_id"], a["lote_id"]) for a in todas
    }


def test_alerta_de_faltante_abierto(cliente, admin, db, ctx):
    pollo = insumo(cliente, admin, "Pollo faltante")
    motor.consumir(
        db,
        ctx,
        tipo_item="insumo",
        item_id=uuid.UUID(pollo["id"]),
        cantidad=D("200"),
        tipo_mov="venta",
        referencia_tipo="venta",
        referencia_id=uuid.uuid4(),
        permitir_faltante=True,
    )
    db.commit()
    (faltante,) = [a for a in alertas(cliente, admin) if a["item_id"] == pollo["id"]]
    assert faltante["tipo"] == "faltante"
    assert "200" in faltante["detalle"]


def test_resumen_de_la_pantalla(cliente, admin, db, ctx):
    # Otras pruebas confirman datos con conexiones reales: se compara contra lo que ya había.
    antes = cliente.get(f"{API}/inventario/resumen", headers=admin).json()
    leche = insumo(cliente, admin, "Leche resumen", minimo="6000")
    lote(db, ctx, leche, "2000", "4")
    fresas = insumo(cliente, admin, "Fresas resumen")
    lote(db, ctx, fresas, "800", "20", vence=hoy() + timedelta(days=2))
    cliente.post(
        f"{API}/mermas",
        headers=admin,
        json={
            "tipo_item": "insumo",
            "item_id": fresas["id"],
            "cantidad": "100",
            "motivo": "danado",
        },
    )
    r = cliente.get(f"{API}/inventario/resumen", headers=admin)
    assert r.status_code == 200, r.text
    k = r.json()
    assert k["valor_inventario"] - antes["valor_inventario"] == 8000 + 14000
    assert set(k["bajo_minimo"]) - set(antes["bajo_minimo"]) == {"Leche resumen"}
    assert k["lotes_por_vencer"] - antes["lotes_por_vencer"] == 1
    assert "Fresas resumen" in k["por_vencer"]
    assert k["mermas_mes"] - antes["mermas_mes"] == 2000


def test_produccion_consulta_el_inventario_y_el_cajero_no(cliente, crear_usuario, login):
    produccion = login(crear_usuario("produccion"))
    assert cliente.get(f"{API}/inventario/stock", headers=produccion).status_code == 200
    cajero = login(crear_usuario("cajero"))
    assert cliente.get(f"{API}/inventario/stock", headers=cajero).status_code == 403


# --- Verificación nocturna (RN-09) ----------------------------------------------------------


def test_verificacion_nocturna_detecta_una_diferencia_hecha_a_mano(cliente, admin, db, ctx):
    harina = insumo(cliente, admin, "Harina verificación")
    bueno = lote(db, ctx, harina, "100", "3")
    malo = lote(db, ctx, harina, "100", "3")
    db.execute(text("UPDATE lotes SET cantidad_disponible = 90 WHERE id = :id"), {"id": malo.id})

    verificaciones = tareas.verificar_inventario(db)
    db.commit()

    registro = db.scalar(
        select(VerificacionInventario).where(VerificacionInventario.sede_id == SEDE_PRINCIPAL)
    )
    assert registro is not None and registro.id in {v.id for v in verificaciones}
    lotes_con_diferencia = {d["lote_id"] for d in registro.diferencias}
    assert str(malo.id) in lotes_con_diferencia and str(bueno.id) not in lotes_con_diferencia
    (alerta,) = [a for a in alertas(cliente, admin) if a["tipo"] == "verificacion"]
    assert "1" in alerta["titulo"]


def test_la_tarea_nocturna_corre_a_la_hora_local_siguiente():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.tareas import proxima_ejecucion

    bogota = ZoneInfo("America/Bogota")
    antes = datetime(2026, 11, 13, 1, 30, tzinfo=bogota)
    despues = datetime(2026, 11, 13, 2, 0, tzinfo=bogota)
    assert proxima_ejecucion(antes, time(2, 0)) == datetime(2026, 11, 13, 2, 0, tzinfo=bogota)
    assert proxima_ejecucion(despues, time(2, 0)) == datetime(2026, 11, 14, 2, 0, tzinfo=bogota)
