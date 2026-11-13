"""Mermas y ajustes por conteo físico (#22)."""

import uuid
from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import select

from app.core.deps import Contexto
from app.modules.auditoria.models import Auditoria
from app.modules.inventario import motor
from app.modules.inventario.models import Lote
from app.shared.fechas import hoy
from tests.conftest import SEDE_PRINCIPAL

API = "/api/v1"


@pytest.fixture
def ctx(crear_usuario) -> Contexto:
    return Contexto(usuario_id=crear_usuario("admin").id, sede_id=SEDE_PRINCIPAL)


def nuevo_insumo(cliente, admin, nombre: str) -> dict:
    return cliente.post(
        f"{API}/insumos", headers=admin, json={"nombre": nombre, "unidad_base": "g"}
    ).json()


def lote(db, ctx, insumo, cantidad: str, costo: str, vence=None) -> Lote:
    lote = motor.crear_lote(
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
        vence=vence,
    )
    db.commit()
    return lote


@pytest.fixture
def azucar(cliente, admin, db, ctx):
    """Azúcar en dos lotes: 500 g a $4 y 1000 g a $5."""
    insumo = nuevo_insumo(cliente, admin, "Azúcar merma")
    lote(db, ctx, insumo, "500", "4")
    lote(db, ctx, insumo, "1000", "5")
    return insumo


def merma(cliente, headers, insumo, cantidad, motivo="danado", **extra):
    return cliente.post(
        f"{API}/mermas",
        headers=headers,
        json={
            "tipo_item": "insumo",
            "item_id": insumo["id"],
            "cantidad": cantidad,
            "motivo": motivo,
        }
        | extra,
    )


def ajuste(cliente, headers, insumo, contada, **extra):
    return cliente.post(
        f"{API}/ajustes",
        headers=headers,
        json={
            "tipo_item": "insumo",
            "item_id": insumo["id"],
            "cantidad_contada": contada,
            "motivo": "Conteo semanal",
        }
        | extra,
    )


def stock(db, insumo) -> D:
    return motor.stock(db, SEDE_PRINCIPAL, "insumo", uuid.UUID(insumo["id"]))


# --- Mermas ---------------------------------------------------------------------------------


def test_merma_consume_peps_y_registra_su_costo(cliente, admin, azucar, db):
    r = merma(cliente, admin, azucar, "700")  # 500 g a $4 + 200 g a $5
    assert r.status_code == 201, r.text
    assert r.json()["costo_total"] == 3000
    assert r.json()["item_nombre"] == "Azúcar merma"
    assert r.json()["lote_id"] is None  # salió de dos lotes
    assert stock(db, azucar) == D(800)


def test_merma_de_un_lote_indicado(cliente, admin, azucar, db):
    nuevo = db.scalars(
        select(Lote)
        .where(Lote.item_id == uuid.UUID(azucar["id"]))
        .order_by(Lote.fecha_ingreso.desc())
    ).first()
    r = merma(cliente, admin, azucar, "100", lote_id=str(nuevo.id))
    assert r.status_code == 201, r.text
    assert (r.json()["costo_total"], r.json()["lote_id"]) == (500, str(nuevo.id))
    db.refresh(nuevo)
    assert nuevo.cantidad_disponible == D(900)


def test_merma_de_un_lote_de_otro_item_no_se_acepta(cliente, admin, azucar, db, ctx):
    otro = nuevo_insumo(cliente, admin, "Sal merma")
    ajeno = lote(db, ctx, otro, "100", "1")
    r = merma(cliente, admin, azucar, "10", lote_id=str(ajeno.id))
    assert r.status_code == 404


def test_un_lote_vencido_se_puede_dar_de_baja(cliente, admin, db, ctx):
    leche = nuevo_insumo(cliente, admin, "Leche merma")
    lote(db, ctx, leche, "1000", "3", vence=hoy() - timedelta(days=1))
    r = merma(cliente, admin, leche, "1000", motivo="vencido")
    assert r.status_code == 201, r.text
    assert r.json()["costo_total"] == 3000
    assert stock(db, leche) == D(0)


def test_merma_mayor_al_stock_no_mueve_nada(cliente, admin, azucar, db):
    r = merma(cliente, admin, azucar, "2000")
    assert (r.status_code, r.json()["codigo"]) == (409, "STOCK_INSUFICIENTE")
    assert "Azúcar merma" in r.json()["mensaje"]
    assert stock(db, azucar) == D(1500)


def test_merma_con_motivo_invalido(cliente, admin, azucar):
    assert merma(cliente, admin, azucar, "1", motivo="robo").status_code == 422


def test_listar_mermas_filtra_por_motivo(cliente, admin, azucar):
    merma(cliente, admin, azucar, "10", motivo="degustacion")
    merma(cliente, admin, azucar, "20", motivo="danado")
    r = cliente.get(
        f"{API}/mermas",
        headers=admin,
        params={"item_id": azucar["id"], "motivo": "degustacion"},
    )
    assert r.status_code == 200
    assert [m["cantidad"] for m in r.json()["items"]] == ["10.0000"]


# --- Ajustes --------------------------------------------------------------------------------


def test_ajuste_negativo_consume_peps(cliente, admin, azucar, db):
    r = ajuste(cliente, admin, azucar, "900")  # faltan 600: 500 a $4 + 100 a $5
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["cantidad_sistema"], body["diferencia"]) == ("1500.0000", "-600.0000")
    assert body["costo_total"] == -2500
    assert stock(db, azucar) == D(900)


def test_ajuste_positivo_usa_el_costo_del_ultimo_lote(cliente, admin, azucar, db):
    r = ajuste(cliente, admin, azucar, "1600")
    assert r.status_code == 201, r.text
    assert (r.json()["diferencia"], r.json()["costo_total"]) == ("100.0000", 500)
    nuevo = db.scalars(
        select(Lote).where(Lote.item_id == uuid.UUID(azucar["id"]), Lote.origen == "ajuste")
    ).one()
    assert nuevo.costo_unitario == D(5)
    assert stock(db, azucar) == D(1600)


def test_ajuste_positivo_sin_lotes_previos_exige_costo(cliente, admin, db):
    canela = nuevo_insumo(cliente, admin, "Canela ajuste")
    r = ajuste(cliente, admin, canela, "50")
    assert (r.status_code, r.json()["codigo"]) == (422, "COSTO_REQUERIDO")
    assert stock(db, canela) == D(0)

    r = ajuste(cliente, admin, canela, "50", costo_unitario="20")
    assert r.status_code == 201, r.text
    assert r.json()["costo_total"] == 1000
    assert stock(db, canela) == D(50)


def test_ajuste_sin_diferencia_es_error(cliente, admin, azucar):
    r = ajuste(cliente, admin, azucar, "1500")
    assert (r.status_code, r.json()["codigo"]) == (422, "SIN_DIFERENCIA")


def test_ajuste_no_cuenta_lo_vencido_pero_lo_informa(cliente, admin, db, ctx):
    queso = nuevo_insumo(cliente, admin, "Queso ajuste")
    vencido = lote(db, ctx, queso, "300", "10", vence=hoy() - timedelta(days=2))
    lote(db, ctx, queso, "200", "12")
    r = ajuste(cliente, admin, queso, "150")
    cuerpo = r.json()
    # Se cuenta solo lo vigente; lo vencido se informa aparte para darlo de baja como merma.
    assert cuerpo["cantidad_sistema"] == "200.0000"
    assert cuerpo["cantidad_vencida"] == "300.0000"
    assert cuerpo["costo_total"] == -600
    db.refresh(vencido)
    assert vencido.cantidad_disponible == D("300")


def test_ajuste_se_puede_listar_con_lo_vencido(cliente, admin, db, ctx):
    leche = nuevo_insumo(cliente, admin, "Leche ajuste")
    lote(db, ctx, leche, "100", "3", vence=hoy() - timedelta(days=1))
    lote(db, ctx, leche, "400", "3")
    ajuste(cliente, admin, leche, "390")
    r = cliente.get(f"{API}/ajustes", headers=admin, params={"item_id": leche["id"]})
    assert r.json()["items"][0]["cantidad_vencida"] == "100.0000"


def test_ajuste_queda_auditado(cliente, admin, azucar, db):
    r = ajuste(cliente, admin, azucar, "1400")
    registro = db.scalars(
        select(Auditoria).where(
            Auditoria.entidad == "ajustes_inventario",
            Auditoria.entidad_id == r.json()["id"],
        )
    ).one()
    assert registro.antes == {"cantidad": "1500.0000"}
    assert registro.despues["diferencia"] == "-100.0000"


def test_reintento_de_ajuste_no_lo_duplica(cliente, admin, azucar, db):
    headers = admin | {"Idempotency-Key": f"ajuste-{uuid.uuid4()}"}
    primero = ajuste(cliente, headers, azucar, "1000")
    segundo = ajuste(cliente, headers, azucar, "1000")
    assert primero.json()["id"] == segundo.json()["id"]
    assert stock(db, azucar) == D(1000)


# --- Permisos -------------------------------------------------------------------------------


def test_produccion_registra_mermas_pero_no_ajustes(cliente, azucar, crear_usuario, login):
    produccion = login(crear_usuario("produccion"))
    assert merma(cliente, produccion, azucar, "5").status_code == 201
    assert ajuste(cliente, produccion, azucar, "1000").status_code == 403


def test_cajero_no_registra_mermas(cliente, azucar, crear_usuario, login):
    cajero = login(crear_usuario("cajero"))
    assert merma(cliente, cajero, azucar, "5").status_code == 403
