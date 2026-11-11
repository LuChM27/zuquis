"""Motor PEPS (#18): casos de los criterios de aceptación, contra PostgreSQL real."""

import threading
import uuid
from datetime import timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import func, select, text

from app.core.db import SesionLocal
from app.core.deps import Contexto
from app.modules.inventario import motor
from app.modules.inventario.models import FaltanteInventario, Insumo, Lote, MovimientoInventario
from app.shared.errores import Conflicto, ErrorNegocio
from app.shared.fechas import hoy
from tests.conftest import SEDE_PRINCIPAL


@pytest.fixture
def ctx(crear_usuario) -> Contexto:
    return Contexto(usuario_id=crear_usuario("admin").id, sede_id=SEDE_PRINCIPAL)


@pytest.fixture
def harina(db) -> Insumo:
    insumo = Insumo(
        sede_id=SEDE_PRINCIPAL, nombre=f"Harina {uuid.uuid4().hex[:6]}", unidad_base="g"
    )
    db.add(insumo)
    db.flush()
    return insumo


def entrar(db, ctx, insumo, cantidad, costo, vence=None):
    return motor.crear_lote(
        db,
        ctx,
        tipo_item="insumo",
        item_id=insumo.id,
        origen="compra",
        origen_id=None,
        cantidad=D(cantidad),
        costo_unitario=D(costo),
        tipo_mov="compra",
        referencia_tipo="compra",
        referencia_id=uuid.uuid4(),
        vence=vence,
    )


def sacar(db, ctx, insumo, cantidad, ref=None, **kw):
    return motor.consumir(
        db,
        ctx,
        tipo_item="insumo",
        item_id=insumo.id,
        cantidad=D(cantidad),
        tipo_mov=kw.pop("tipo_mov", "consumo_produccion"),
        referencia_tipo="prueba",
        referencia_id=ref or uuid.uuid4(),
        **kw,
    )


def invariante(db, ctx, insumo):
    """RN-09: Σ lotes = Σ movimientos para el ítem."""
    en_lotes = motor.stock(db, ctx.sede_id, "insumo", insumo.id)
    en_libro = db.scalar(
        select(func.coalesce(func.sum(MovimientoInventario.cantidad), 0)).where(
            MovimientoInventario.item_id == insumo.id
        )
    )
    assert en_lotes == D(en_libro)


def test_un_lote(db, ctx, harina):
    entrar(db, ctx, harina, "1000", "3.000000")
    r = sacar(db, ctx, harina, "250")
    assert r.costo_total == 750
    assert [c.cantidad for c in r.consumos] == [D("250")]
    assert motor.stock(db, ctx.sede_id, "insumo", harina.id) == D("750")
    invariante(db, ctx, harina)


def test_varios_lotes_con_costos_distintos_se_consumen_por_peps(db, ctx, harina):
    viejo = entrar(db, ctx, harina, "1000", "3.000000")
    nuevo = entrar(db, ctx, harina, "1000", "4.000000")
    r = sacar(db, ctx, harina, "1500")
    # 1000 g a $3 + 500 g a $4, una fila de movimiento por lote
    assert [(c.lote_id, c.cantidad, c.costo_total) for c in r.consumos] == [
        (viejo.id, D("1000"), 3000),
        (nuevo.id, D("500"), 2000),
    ]
    assert r.costo_total == 5000
    invariante(db, ctx, harina)


def test_consumo_que_agota_exactamente_un_lote(db, ctx, harina):
    viejo = entrar(db, ctx, harina, "500", "3.000000")
    entrar(db, ctx, harina, "500", "4.000000")
    r = sacar(db, ctx, harina, "500")
    assert [c.lote_id for c in r.consumos] == [viejo.id]
    db.refresh(viejo)
    assert viejo.cantidad_disponible == 0


def test_consumo_mayor_al_stock_no_mueve_nada(db, ctx, harina):
    lote = entrar(db, ctx, harina, "100", "3.000000")
    with pytest.raises(motor.StockInsuficiente) as error:
        sacar(db, ctx, harina, "100.0001")
    assert error.value.detalle == {
        "tipo_item": "insumo",
        "item_id": str(harina.id),
        "requerido": "100.0001",
        "disponible": "100.0000",
    }
    db.refresh(lote)
    assert lote.cantidad_disponible == D("100")


def test_lote_vencido_se_ignora_salvo_para_merma(db, ctx, harina):
    vencido = entrar(db, ctx, harina, "100", "2.000000", vence=hoy() - timedelta(days=1))
    vigente = entrar(db, ctx, harina, "100", "3.000000", vence=hoy())
    r = sacar(db, ctx, harina, "50")
    assert [c.lote_id for c in r.consumos] == [vigente.id]
    with pytest.raises(motor.StockInsuficiente):
        sacar(db, ctx, harina, "100")  # quedan 50 vigentes
    merma = sacar(db, ctx, harina, "100", tipo_mov="merma", incluir_vencidos=True)
    assert [c.lote_id for c in merma.consumos] == [vencido.id]


def test_costo_por_linea_se_redondea_una_vez(db, ctx, harina):
    entrar(db, ctx, harina, "3", "0.333333")
    r = sacar(db, ctx, harina, "1.5")
    assert r.costo_total == 0  # 1,5 × 0,333333 = 0,4999995 → 0
    r = sacar(db, ctx, harina, "1.5")
    assert r.costo_total == 0


def test_reverso_devuelve_a_los_lotes_originales_con_su_costo(db, ctx, harina):
    viejo = entrar(db, ctx, harina, "1000", "3.000000")
    nuevo = entrar(db, ctx, harina, "1000", "4.000000")
    ref = uuid.uuid4()
    sacar(db, ctx, harina, "1500", ref=ref)
    entrar(db, ctx, harina, "1000", "9.000000")  # un lote nuevo no cambia a dónde vuelve
    reversos = motor.reversar(db, ctx, "prueba", ref)
    assert sorted((r.lote_id, r.cantidad, r.costo_total) for r in reversos) == sorted(
        [(viejo.id, D("1000"), 3000), (nuevo.id, D("500"), 2000)]
    )
    db.refresh(viejo)
    db.refresh(nuevo)
    assert viejo.cantidad_disponible == nuevo.cantidad_disponible == D("1000")
    with pytest.raises(Conflicto, match="ya se anuló"):
        motor.reversar(db, ctx, "prueba", ref)
    invariante(db, ctx, harina)


def test_reverso_de_una_entrada_ya_consumida_se_rechaza(db, ctx, harina):
    lote = entrar(db, ctx, harina, "100", "3.000000")
    sacar(db, ctx, harina, "10")
    ref = db.scalar(
        select(MovimientoInventario.referencia_id).where(
            MovimientoInventario.lote_id == lote.id, MovimientoInventario.tipo == "compra"
        )
    )
    with pytest.raises(Conflicto) as error:
        motor.reversar(db, ctx, "compra", ref)
    assert error.value.codigo == "LOTE_CONSUMIDO"


def test_ajuste_positivo_al_costo_del_ultimo_lote(db, ctx, harina):
    with pytest.raises(ErrorNegocio) as error:
        motor.ajuste_positivo(
            db,
            ctx,
            tipo_item="insumo",
            item_id=harina.id,
            cantidad=D("10"),
            referencia_id=uuid.uuid4(),
        )
    assert error.value.codigo == "COSTO_REQUERIDO"
    entrar(db, ctx, harina, "100", "3.000000")
    entrar(db, ctx, harina, "100", "4.500000")
    lote = motor.ajuste_positivo(
        db, ctx, tipo_item="insumo", item_id=harina.id, cantidad=D("10"), referencia_id=uuid.uuid4()
    )
    assert lote.origen == "ajuste"
    assert lote.costo_unitario == D("4.500000")


def test_faltante_se_regulariza_con_el_lote_siguiente(db, ctx, harina):
    entrar(db, ctx, harina, "100", "3.000000")
    venta = uuid.uuid4()
    r = sacar(db, ctx, harina, "150", ref=venta, tipo_mov="venta", permitir_faltante=True)
    assert r.faltante == D("50")
    assert motor.stock(db, ctx.sede_id, "insumo", harina.id) == 0  # nunca negativo
    faltante = db.scalar(
        select(FaltanteInventario).where(FaltanteInventario.referencia_id == venta)
    )
    assert (faltante.estado, faltante.costo_estimado) == ("abierto", 150)  # 50 g al último costo

    nuevo = entrar(db, ctx, harina, "100", "4.000000")
    db.refresh(faltante)
    db.refresh(nuevo)
    assert faltante.estado == "regularizado"
    assert nuevo.cantidad_disponible == D("50")
    real = db.scalar(
        select(MovimientoInventario).where(
            MovimientoInventario.id == faltante.regularizado_por_mov_id
        )
    )
    assert (real.referencia_id, real.costo_total) == (venta, -200)  # costo real: 50 g a $4
    invariante(db, ctx, harina)


def test_el_libro_de_movimientos_es_de_solo_insercion(db, ctx, harina):
    entrar(db, ctx, harina, "100", "3.000000")
    with pytest.raises(Exception, match="solo inserción"):
        db.execute(text("UPDATE movimientos_inventario SET cantidad = 1"))
    db.rollback()


def test_verificacion_detecta_una_diferencia_hecha_a_mano(db, ctx, harina):
    lote = entrar(db, ctx, harina, "100", "3.000000")
    _, diferencias = motor.verificar(db, ctx.sede_id)
    assert not [d for d in diferencias if d["lote_id"] == str(lote.id)]
    db.execute(text("UPDATE lotes SET cantidad_disponible = 90 WHERE id = :id"), {"id": lote.id})
    _, diferencias = motor.verificar(db, ctx.sede_id)
    assert [d for d in diferencias if d["lote_id"] == str(lote.id)] == [
        {
            "lote_id": str(lote.id),
            "tipo_item": "insumo",
            "item_id": str(harina.id),
            "en_lote": "90.0000",
            "en_movimientos": "100.0000",
        }
    ]


def test_dos_consumos_simultaneos_no_dejan_cantidad_negativa(crear_usuario):
    """Conexiones reales: el segundo espera el bloqueo del lote y ve lo que dejó el primero."""
    with SesionLocal() as s:
        usuario = crear_usuario_real(s)
        insumo = Insumo(
            sede_id=SEDE_PRINCIPAL, nombre=f"Azúcar {uuid.uuid4().hex[:6]}", unidad_base="g"
        )
        s.add(insumo)
        s.flush()
        ctx = Contexto(usuario_id=usuario, sede_id=SEDE_PRINCIPAL)
        entrar(s, ctx, insumo, "100", "1.000000")
        s.commit()
        insumo_id = insumo.id

    resultados: list[str] = []
    barrera = threading.Barrier(2)

    def consumir():
        with SesionLocal() as s:
            ctx = Contexto(usuario_id=usuario, sede_id=SEDE_PRINCIPAL)
            barrera.wait()
            try:
                motor.consumir(
                    s,
                    ctx,
                    tipo_item="insumo",
                    item_id=insumo_id,
                    cantidad=D("70"),
                    tipo_mov="consumo_produccion",
                    referencia_tipo="prueba",
                    referencia_id=uuid.uuid4(),
                )
                s.commit()
                resultados.append("ok")
            except motor.StockInsuficiente:
                s.rollback()
                resultados.append("sin_stock")

    hilos = [threading.Thread(target=consumir) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=15)

    assert sorted(resultados) == ["ok", "sin_stock"]
    with SesionLocal() as s:
        lote = s.scalar(select(Lote).where(Lote.item_id == insumo_id))
        assert lote.cantidad_disponible == D("30")


def crear_usuario_real(s) -> uuid.UUID:
    from app.core.seguridad import hashear_clave
    from app.modules.auth.models import Usuario

    u = Usuario(
        nombre="Concurrencia",
        email=f"{uuid.uuid4().hex[:8]}@zuquis.test",
        password_hash=hashear_clave("x" * 10),
    )
    s.add(u)
    s.flush()
    return u.id
