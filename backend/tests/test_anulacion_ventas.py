"""Anulación de ventas (#31, RF-15, RN-01, RN-03, RN-04, RN-12)."""

import uuid
from decimal import Decimal as D

import pytest
from sqlalchemy import select, text

from app.modules.caja.models import CajaMovimiento
from app.modules.inventario.models import Lote, MovimientoInventario
from tests.fixtures_ventas import API, esperado, stock, vender, venta_mockup


def anular(cliente, headers, venta, motivo="El cliente se arrepintió"):
    return cliente.post(
        f"{API}/ventas/{venta['id']}/anular", headers=headers, json={"motivo": motivo}
    )


def cerrar_caja(db):
    """Cierra la caja abierta directamente (el cierre con arqueo llega en #32)."""
    db.execute(
        text(
            "UPDATE caja_sesiones SET estado = 'cerrada', cerrada_en = now() "
            "WHERE estado = 'abierta'"
        )
    )
    db.commit()


def test_anular_marca_la_venta_sin_borrarla(cliente, admin, carta, metodos, caja_abierta):
    v = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    r = anular(cliente, admin, v)
    assert r.status_code == 200, r.text
    anulada = r.json()
    assert (anulada["estado"], anulada["motivo_anulacion"], anulada["numero"]) == (
        "anulada",
        "El cliente se arrepintió",
        v["numero"],
    )
    assert anulada["anulada_en"] is not None
    assert cliente.get(f"{API}/ventas/{v['id']}", headers=admin).json()["estado"] == "anulada"


def test_el_inventario_vuelve_a_los_mismos_lotes(cliente, admin, carta, metodos, caja_abierta, db):
    v = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    lotes_pastel = db.scalars(
        select(MovimientoInventario.lote_id).where(
            MovimientoInventario.referencia_id == uuid.UUID(v["id"]),
            MovimientoInventario.item_id == uuid.UUID(carta["pastel"]["id"]),
        )
    ).all()
    anular(cliente, admin, v)
    assert stock(db, "producto", carta["pastel"]["id"]) == D("12")
    assert stock(db, "insumo", carta["insumos"]["Leche venta"]) == D("10000")
    db.expire_all()
    assert all(db.get(Lote, lote_id).cantidad_disponible == D("12") for lote_id in lotes_pastel)


def test_la_caja_recibe_el_reverso_por_metodo(cliente, admin, carta, metodos, caja_abierta, db):
    v = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    anular(cliente, admin, v)
    assert esperado(cliente, admin) == {**{n: 0 for n in metodos}, "Efectivo": 100000}
    reversos = (
        db.execute(
            select(CajaMovimiento.monto)
            .where(
                CajaMovimiento.referencia_id == uuid.UUID(v["id"]),
                CajaMovimiento.tipo == "reverso_anulacion",
            )
            .order_by(CajaMovimiento.monto)
        )
        .scalars()
        .all()
    )
    assert reversos == [-28500, -20000]


def test_anulada_despues_del_cierre_el_reverso_va_a_la_caja_nueva(
    cliente, admin, carta, metodos, caja_abierta, db
):
    v = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    cerrar_caja(db)
    cliente.post(f"{API}/caja/abrir", headers=admin, json={"base_inicial": 50000})
    r = anular(cliente, admin, v)
    assert r.status_code == 200, r.text
    nueva = cliente.get(f"{API}/caja/actual", headers=admin).json()["sesion"]["id"]
    caja_reverso = db.scalars(
        select(CajaMovimiento.caja_sesion_id).where(
            CajaMovimiento.referencia_id == uuid.UUID(v["id"]),
            CajaMovimiento.tipo == "reverso_anulacion",
        )
    ).all()
    assert set(map(str, caja_reverso)) == {nueva}
    assert esperado(cliente, admin)["Efectivo"] == 50000 - 28500
    assert stock(db, "producto", carta["pastel"]["id"]) == D("12")


def test_sin_caja_abierta_no_se_anula(cliente, admin, carta, metodos, caja_abierta, db):
    v = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    cerrar_caja(db)
    r = anular(cliente, admin, v)
    assert (r.status_code, r.json()["codigo"]) == (409, "CAJA_CERRADA")
    assert cliente.get(f"{API}/ventas/{v['id']}", headers=admin).json()["estado"] == "pagada"


def test_no_se_anula_dos_veces(cliente, admin, carta, metodos, caja_abierta):
    v = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    anular(cliente, admin, v)
    r = anular(cliente, admin, v)
    assert (r.status_code, r.json()["codigo"]) == (409, "YA_ANULADO")


def test_el_numero_no_se_reutiliza(cliente, admin, carta, metodos, caja_abierta):
    v = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    anular(cliente, admin, v)
    siguiente = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    assert siguiente["numero"] == v["numero"] + 1


def test_anular_exige_motivo_y_permiso(
    cliente, admin, carta, metodos, caja_abierta, crear_usuario, login
):
    v = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    assert anular(cliente, admin, v, motivo="").status_code == 422
    cajero = login(crear_usuario("cajero"))
    assert anular(cliente, cajero, v).status_code == 403


def test_no_existe_delete_sobre_ventas(cliente, admin, carta, metodos, caja_abierta):
    v = vender(cliente, admin, venta_mockup(carta, metodos)).json()
    assert cliente.delete(f"{API}/ventas/{v['id']}", headers=admin).status_code == 405


@pytest.mark.parametrize("tabla", ["caja_movimientos", "movimientos_inventario"])
def test_los_libros_no_admiten_borrado(cliente, admin, carta, metodos, caja_abierta, db, tabla):
    vender(cliente, admin, venta_mockup(carta, metodos))
    with pytest.raises(Exception, match="no se puede"):
        db.execute(text(f"DELETE FROM {tabla}"))  # noqa: S608
    db.rollback()


def test_anular_una_venta_con_faltante_lo_cierra(cliente, admin, carta, metodos, caja_abierta, db):
    cliente.patch(f"{API}/configuracion", headers=admin, json={"permitir_venta_sin_stock": True})
    datos = {
        "tipo_servicio": "local",
        "items": [{"producto_id": carta["croissant"]["id"], "cantidad": "10"}],
        "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 75000}],
    }
    v = vender(cliente, admin, datos).json()
    assert anular(cliente, admin, v).status_code == 200
    assert stock(db, "producto", carta["croissant"]["id"]) == D("8")
    pendientes = db.execute(
        text(
            "SELECT count(*) FROM faltantes_inventario "
            "WHERE estado = 'abierto' AND referencia_id = :v"
        ),
        {"v": v["id"]},
    ).scalar()
    assert pendientes == 0
