"""Encargos: creación, ítems, estados, abonos, entrega y cancelación (#41, #42)."""

from decimal import Decimal as D

import pytest
from sqlalchemy import text

from tests.fixtures_encargos import (
    abonar,
    abrir_caja,
    alistar,
    cancelar,
    cerrar_cuadrada,
    crear_encargo,
    entregar,
    estado,
    torta,
)
from tests.fixtures_ventas import API, esperado, stock


@pytest.fixture
def encargo(cliente, admin, cliente_a):
    r = crear_encargo(cliente, admin, torta(cliente_a["id"]))
    assert r.status_code == 201, r.text
    return r.json()


def ver(cliente, headers, encargo):
    return cliente.get(f"{API}/encargos/{encargo['id']}", headers=headers).json()


def movimientos(cliente, headers):
    r = cliente.get(f"{API}/caja/actual/movimientos", headers=headers).json()
    return sorted((m["tipo"], m["metodo"], m["monto"]) for m in r)


# --- Creación y edición (#41) ---------------------------------------------------------------


def test_crear_con_numero_consecutivo_y_saldo(cliente, admin, cliente_a, encargo):
    assert (encargo["numero"], encargo["estado"], encargo["editable"]) == (1, "pendiente", True)
    assert (encargo["total"], encargo["abonado"], encargo["saldo"]) == (90000, 0, 90000)
    assert encargo["cliente"]["nombre"] == "Cliente A"
    assert encargo["tipo_entrega"] == "recoge"
    otro = crear_encargo(cliente, admin, torta(cliente_a["id"])).json()
    assert otro["numero"] == 2


def test_items_de_la_carta_y_personalizados(cliente, admin, cliente_a, carta):
    r = crear_encargo(
        cliente,
        admin,
        {
            "cliente_id": cliente_a["id"],
            "fecha_entrega": "2026-10-16T18:30:00-05:00",
            "items": [
                {"producto_id": carta["pastel"]["id"], "cantidad": "24"},
                {"producto_id": carta["croissant"]["id"], "cantidad": "2", "precio": 7000},
                {"descripcion": "Decoración con nombre", "cantidad": "1", "precio": 15000},
            ],
        },
    )
    assert r.status_code == 201, r.text
    e = r.json()
    assert [(i["descripcion"], i["precio"], i["subtotal"]) for i in e["items"]] == [
        ("Pastel de pollo", 4500, 108000),
        ("Croissant de jamón y queso", 7000, 14000),
        ("Decoración con nombre", 15000, 15000),
    ]
    assert e["total"] == 137000
    assert e["descripcion"] == (
        "24 × Pastel de pollo, 2 × Croissant de jamón y queso, Decoración con nombre"
    )


def test_un_item_sin_producto_exige_descripcion_y_precio(cliente, admin, cliente_a):
    datos = torta(cliente_a["id"], items=[{"cantidad": "1", "precio": 1000}])
    assert crear_encargo(cliente, admin, datos).status_code == 422
    datos = torta(cliente_a["id"], items=[{"descripcion": "Torta", "cantidad": "1"}])
    assert crear_encargo(cliente, admin, datos).status_code == 422


def test_a_domicilio_usa_la_direccion_del_cliente(cliente, admin, cliente_a):
    e = crear_encargo(cliente, admin, torta(cliente_a["id"], tipo_entrega="domicilio")).json()
    assert e["direccion_entrega"] == "Cra 10 # 5-20"


def test_editar_mientras_esta_pendiente(cliente, admin, encargo):
    r = cliente.patch(
        f"{API}/encargos/{encargo['id']}",
        headers=admin,
        json={
            "fecha_entrega": "2026-10-17T10:00:00-05:00",
            "observaciones": "Sin nueces",
            "items": [
                {"descripcion": "Torta de cumpleaños 2 lb", "cantidad": "1", "precio": 150000}
            ],
        },
    )
    assert r.status_code == 200, r.text
    e = r.json()
    assert (e["total"], e["saldo"], e["observaciones"]) == (150000, 150000, "Sin nueces")
    assert e["fecha_entrega"].startswith("2026-10-17T10:00")


def test_rn23_en_produccion_no_se_edita(cliente, admin, encargo):
    assert estado(cliente, admin, encargo, "en_produccion").json()["editable"] is False
    r = cliente.patch(
        f"{API}/encargos/{encargo['id']}", headers=admin, json={"observaciones": "Cambio"}
    )
    assert (r.status_code, r.json()["codigo"]) == (409, "ENCARGO_EN_PRODUCCION")
    assert r.json()["mensaje"] == (
        "El encargo ya pasó a producción; solo un administrador puede cancelarlo"
    )


# --- Estados (#41) --------------------------------------------------------------------------

ESTADOS = ("pendiente", "en_produccion", "listo", "entregado", "cancelado")
VALIDAS = {("pendiente", "en_produccion"), ("en_produccion", "listo")}


def _llevar_a(cliente, admin, encargo, estado_inicial):
    if estado_inicial in ("en_produccion", "listo", "entregado"):
        estado(cliente, admin, encargo, "en_produccion")
    if estado_inicial in ("listo", "entregado"):
        estado(cliente, admin, encargo, "listo")
    if estado_inicial == "entregado":
        r = entregar(
            cliente,
            admin,
            encargo,
            [{"metodo_pago_id": _efectivo(cliente, admin), "monto": 90000}],
        )
        assert r.status_code == 200, r.text
    if estado_inicial == "cancelado":
        assert cancelar(cliente, admin, encargo).status_code == 200


def _efectivo(cliente, admin):
    return next(
        m["id"]
        for m in cliente.get(f"{API}/metodos-pago", headers=admin).json()
        if m["nombre"] == "Efectivo"
    )


@pytest.mark.parametrize("de", ESTADOS)
@pytest.mark.parametrize("a", ESTADOS)
def test_transiciones_por_el_endpoint_de_estado(cliente, admin, encargo, caja_abierta, de, a):
    """Solo se avanza un paso: pendiente → en producción → listo. Entregar y cancelar tienen
    su propia operación, y un encargo entregado o cancelado ya no se mueve."""
    _llevar_a(cliente, admin, encargo, de)
    r = estado(cliente, admin, encargo, a)
    if (de, a) in VALIDAS:
        assert r.status_code == 200, r.text
        assert r.json()["estado"] == a
    else:
        assert (r.status_code, r.json()["codigo"]) == (409, "TRANSICION_INVALIDA")
        assert ver(cliente, admin, encargo)["estado"] == de


@pytest.mark.parametrize("de", ["pendiente", "en_produccion"])
def test_no_se_entrega_sin_estar_listo(cliente, admin, encargo, caja_abierta, de):
    _llevar_a(cliente, admin, encargo, de)
    r = entregar(
        cliente, admin, encargo, [{"metodo_pago_id": _efectivo(cliente, admin), "monto": 90000}]
    )
    assert (r.status_code, r.json()["codigo"]) == (409, "TRANSICION_INVALIDA")


@pytest.mark.parametrize("de", ["pendiente", "en_produccion", "listo"])
def test_se_cancela_desde_cualquier_estado_antes_de_entregado(cliente, admin, encargo, de):
    _llevar_a(cliente, admin, encargo, de)
    r = cancelar(cliente, admin, encargo)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cancelado"


@pytest.mark.parametrize("de", ["entregado", "cancelado"])
def test_entregado_o_cancelado_ya_no_se_cancela_ni_abona(
    cliente, admin, encargo, caja_abierta, metodos, de
):
    _llevar_a(cliente, admin, encargo, de)
    assert cancelar(cliente, admin, encargo).json()["codigo"] == "ENCARGO_CERRADO"
    r = abonar(cliente, admin, encargo, 1000, metodos["Efectivo"])
    assert r.json()["codigo"] == "ENCARGO_CERRADO"


# --- Listado y conteo (#41) -----------------------------------------------------------------


def test_listado_por_fecha_de_entrega_y_conteo_de_la_semana(cliente, admin, cliente_a):
    for fecha in ("2026-10-12T10:00", "2026-10-16T14:00", "2026-10-16T23:30", "2026-10-18T09:00"):
        crear_encargo(cliente, admin, torta(cliente_a["id"], fecha_entrega=f"{fecha}:00-05:00"))
    cancelado = crear_encargo(
        cliente, admin, torta(cliente_a["id"], fecha_entrega="2026-10-16T20:00:00-05:00")
    ).json()
    cancelar(cliente, admin, cancelado)

    del_16 = cliente.get(
        f"{API}/encargos", headers=admin, params={"desde": "2026-10-16", "hasta": "2026-10-16"}
    ).json()
    assert [e["fecha_entrega"][11:16] for e in del_16["items"]] == ["14:00", "20:00", "23:30"]

    semana = cliente.get(
        f"{API}/encargos/conteo",
        headers=admin,
        params={"desde": "2026-10-12", "hasta": "2026-10-18"},
    ).json()
    assert [(d["fecha"][-2:], d["encargos"]) for d in semana] == [
        ("12", 1),
        ("13", 0),
        ("14", 0),
        ("15", 0),
        ("16", 2),
        ("17", 0),
        ("18", 1),
    ]


def test_buscar_por_numero_cliente_o_descripcion(cliente, admin, cliente_a, encargo):
    def buscar(q):
        r = cliente.get(f"{API}/encargos", headers=admin, params={"q": q})
        return [e["numero"] for e in r.json()["items"]]

    assert buscar("0001") == [1]
    assert buscar("cumple") == [1]
    assert buscar("cliente a") == [1]
    assert buscar("galletas") == []


# --- Abonos (#42, RN-19, RN-20) -------------------------------------------------------------


def test_abonar_requiere_caja_abierta(cliente, admin, encargo, metodos):
    r = abonar(cliente, admin, encargo, 45000, metodos["Nequi"])
    assert (r.status_code, r.json()["codigo"]) == (409, "CAJA_CERRADA")


def test_el_abono_entra_a_la_caja_y_baja_el_saldo(cliente, admin, encargo, metodos, caja_abierta):
    r = abonar(cliente, admin, encargo, 45000, metodos["Nequi"])
    assert r.status_code == 201, r.text
    e = r.json()
    assert (e["abonado"], e["saldo"]) == (45000, 45000)
    assert [(a["monto"], a["metodo"], a["estado"]) for a in e["abonos"]] == [
        (45000, "Nequi", "vigente")
    ]
    assert movimientos(cliente, admin) == [("abono", "Nequi", 45000)]
    # No es venta hasta que se entregue (RN-20).
    assert cliente.get(f"{API}/ventas/resumen", headers=admin).json()["total"] == 0


def test_abono_que_supera_el_saldo(cliente, admin, encargo, metodos, caja_abierta):
    abonar(cliente, admin, encargo, 45000, metodos["Nequi"])
    r = abonar(cliente, admin, encargo, 45001, metodos["Efectivo"])
    assert (r.status_code, r.json()["codigo"]) == (422, "ABONO_EXCEDE_SALDO")
    assert r.json()["detalle"] == {"saldo": 45000, "abono": 45001}
    assert abonar(cliente, admin, encargo, 45000, metodos["Efectivo"]).json()["saldo"] == 0


def test_crear_con_abono_inicial(cliente, admin, cliente_a, metodos, caja_abierta):
    datos = torta(cliente_a["id"], abono={"monto": 30000, "metodo_pago_id": metodos["Efectivo"]})
    e = crear_encargo(cliente, admin, datos).json()
    assert (e["abonado"], e["saldo"]) == (30000, 60000)
    assert esperado(cliente, admin)["Efectivo"] == 130000


def test_crear_con_abono_y_caja_cerrada_no_deja_el_encargo(cliente, admin, cliente_a, metodos):
    datos = torta(cliente_a["id"], abono={"monto": 30000, "metodo_pago_id": metodos["Efectivo"]})
    r = crear_encargo(cliente, admin, datos)
    assert (r.status_code, r.json()["codigo"]) == (409, "CAJA_CERRADA")
    assert cliente.get(f"{API}/encargos", headers=admin).json()["total"] == 0


def test_reintentar_un_abono_no_lo_duplica(cliente, admin, encargo, metodos, caja_abierta):
    headers = admin | {"Idempotency-Key": "abono-repetido-1"}
    cuerpo = {"monto": 20000, "metodo_pago_id": metodos["Efectivo"]}
    for _ in range(2):
        r = cliente.post(f"{API}/encargos/{encargo['id']}/abonos", headers=headers, json=cuerpo)
        assert r.status_code == 201, r.text
    assert ver(cliente, admin, encargo)["abonado"] == 20000


def test_anular_un_abono_devuelve_el_dinero(cliente, admin, encargo, metodos, caja_abierta):
    e = abonar(cliente, admin, encargo, 45000, metodos["Nequi"]).json()
    r = cliente.post(
        f"{API}/encargos/{e['id']}/abonos/{e['abonos'][0]['id']}/anular",
        headers=admin,
        json={"motivo": "Se registró en el encargo equivocado"},
    )
    assert r.status_code == 200, r.text
    assert (r.json()["abonado"], r.json()["saldo"]) == (0, 90000)
    assert r.json()["abonos"][0]["estado"] == "anulado"
    assert esperado(cliente, admin)["Nequi"] == 0


def test_anular_abonos_pide_permiso(
    cliente, admin, encargo, metodos, caja_abierta, crear_usuario, login
):
    e = abonar(cliente, admin, encargo, 45000, metodos["Nequi"]).json()
    cajero = login(crear_usuario("cajero"))
    r = cliente.post(
        f"{API}/encargos/{e['id']}/abonos/{e['abonos'][0]['id']}/anular",
        headers=cajero,
        json={"motivo": "Error al registrar"},
    )
    assert r.status_code == 403


# --- Entrega (#42, RN-21) -------------------------------------------------------------------


def test_ejemplo_del_mockup_abono_45000_y_se_cobran_45000(
    cliente, admin, encargo, metodos, caja_abierta
):
    """Total $90.000, abono $45.000 por Nequi ⇒ entregar y cobrar $45.000."""
    abonar(cliente, admin, encargo, 45000, metodos["Nequi"])
    listo = alistar(cliente, admin, encargo)
    assert listo["saldo"] == 45000

    corto = entregar(
        cliente, admin, encargo, [{"metodo_pago_id": metodos["Efectivo"], "monto": 90000}]
    )
    assert (corto.status_code, corto.json()["codigo"]) == (422, "PAGOS_NO_CUADRAN")

    r = entregar(cliente, admin, encargo, [{"metodo_pago_id": metodos["Efectivo"], "monto": 45000}])
    assert r.status_code == 200, r.text
    e = r.json()
    assert (e["estado"], e["saldo"], e["venta_numero"]) == ("entregado", 0, 1)

    venta = cliente.get(f"{API}/ventas/{e['venta_id']}", headers=admin).json()
    assert (venta["total"], venta["abonos_aplicados"], venta["cobrado"]) == (90000, 45000, 45000)
    assert (venta["encargo_numero"], venta["cliente"], venta["tipo_servicio"]) == (
        1,
        "Cliente A",
        "llevar",
    )
    assert [(i["producto"], i["producto_id"], i["subtotal"]) for i in venta["items"]] == [
        ("Torta de cumpleaños 1 lb", None, 90000)
    ]
    assert movimientos(cliente, admin) == [
        ("abono", "Nequi", 45000),
        ("saldo_encargo", "Efectivo", 45000),
    ]
    resumen = cliente.get(f"{API}/ventas/resumen", headers=admin).json()
    assert (resumen["ventas"], resumen["total"]) == (1, 90000)
    assert [(p["producto"], p["valor"]) for p in resumen["productos"]] == [
        ("Torta de cumpleaños 1 lb", 90000)
    ]


def test_el_abono_va_a_su_caja_y_la_venta_al_dia_de_entrega(
    cliente, admin, encargo, metodos, caja_abierta, db
):
    """Dos cajas distintas: el abono cuenta en la primera, la venta en la segunda (RN-20)."""
    abonar(cliente, admin, encargo, 45000, metodos["Nequi"])
    alistar(cliente, admin, encargo)
    primera = cerrar_cuadrada(cliente, admin)
    assert primera["Nequi"] == 45000
    cajas = cliente.get(f"{API}/caja/sesiones", headers=admin).json()["items"]
    resumen_1 = cliente.get(f"{API}/caja/sesiones/{cajas[0]['id']}", headers=admin).json()[
        "resumen"
    ]
    assert (resumen_1["ventas"], resumen_1["abonos"]) == (0, 45000)

    abrir_caja(cliente, admin, base=50000)
    e = entregar(
        cliente, admin, encargo, [{"metodo_pago_id": metodos["Efectivo"], "monto": 45000}]
    ).json()
    segunda = cliente.get(f"{API}/caja/actual", headers=admin).json()
    venta = cliente.get(f"{API}/ventas/{e['venta_id']}", headers=admin).json()
    assert venta["caja_sesion_id"] == segunda["sesion"]["id"]
    assert {x["metodo"]: x["esperado"] for x in segunda["esperado"]}["Efectivo"] == 95000
    del_turno = cliente.get(
        f"{API}/ventas", headers=admin, params={"caja_sesion_id": segunda["sesion"]["id"]}
    ).json()
    assert [v["total"] for v in del_turno["items"]] == [90000]


def test_entregar_descuenta_inventario_de_los_productos(
    cliente, admin, cliente_a, carta, metodos, caja_abierta, db
):
    e = crear_encargo(
        cliente,
        admin,
        {
            "cliente_id": cliente_a["id"],
            "fecha_entrega": "2026-10-16T18:30:00-05:00",
            "items": [
                {"producto_id": carta["pastel"]["id"], "cantidad": "10", "precio": 4000},
                {"descripcion": "Caja decorada", "cantidad": "1", "precio": 5000},
            ],
        },
    ).json()
    alistar(cliente, admin, e)
    r = entregar(cliente, admin, e, [{"metodo_pago_id": metodos["Efectivo"], "monto": 45000}])
    assert r.status_code == 200, r.text
    assert stock(db, "producto", carta["pastel"]["id"]) == D("2")
    venta = cliente.get(f"{API}/ventas/{r.json()['venta_id']}", headers=admin).json()
    # 10 pasteles de un lote a $675: costo real por PEPS; el ítem personalizado no tiene costo.
    assert (venta["total"], venta["costo_total"]) == (45000, 6750)
    assert [(i["precio_unitario"], i["costo_total"]) for i in venta["items"]] == [
        (4000, 6750),
        (5000, 0),
    ]


def test_encargo_pagado_del_todo_se_entrega_sin_pagos(
    cliente, admin, encargo, metodos, caja_abierta
):
    abonar(cliente, admin, encargo, 90000, metodos["Nequi"])
    alistar(cliente, admin, encargo)
    r = entregar(cliente, admin, encargo, [])
    assert r.status_code == 200, r.text
    venta = cliente.get(f"{API}/ventas/{r.json()['venta_id']}", headers=admin).json()
    assert (venta["total"], venta["cobrado"], venta["pagos"]) == (90000, 0, [])


def test_entrega_a_domicilio_crea_el_domicilio(
    cliente, admin, cliente_a, domiciliario, metodos, caja_abierta
):
    e = crear_encargo(cliente, admin, torta(cliente_a["id"], tipo_entrega="domicilio")).json()
    alistar(cliente, admin, e)
    pagos = [{"metodo_pago_id": metodos["Efectivo"], "monto": 95000}]
    sin_domiciliario = entregar(cliente, admin, e, pagos, valor_domicilio=5000)
    assert sin_domiciliario.status_code == 422
    r = entregar(
        cliente,
        admin,
        e,
        pagos,
        valor_domicilio=5000,
        domicilio={"domiciliario_id": domiciliario["id"], "direccion": e["direccion_entrega"]},
    )
    assert r.status_code == 200, r.text
    (d,) = cliente.get(f"{API}/domicilios", headers=admin).json()
    assert (d["encargo_numero"], d["valor"], d["cliente"], d["total_venta"]) == (
        e["numero"],
        5000,
        "Cliente A",
        90000,
    )
    assert movimientos(cliente, admin) == [
        ("domicilio", "Efectivo", 5000),
        ("saldo_encargo", "Efectivo", 90000),
    ]


def test_anular_la_venta_de_un_encargo_lo_deja_listo(
    cliente, admin, encargo, metodos, caja_abierta
):
    abonar(cliente, admin, encargo, 45000, metodos["Nequi"])
    alistar(cliente, admin, encargo)
    e = entregar(
        cliente, admin, encargo, [{"metodo_pago_id": metodos["Efectivo"], "monto": 45000}]
    ).json()
    r = cliente.post(
        f"{API}/ventas/{e['venta_id']}/anular", headers=admin, json={"motivo": "Se entregó otro"}
    )
    assert r.status_code == 200, r.text
    e = ver(cliente, admin, encargo)
    assert (e["estado"], e["venta_id"], e["abonado"], e["saldo"]) == ("listo", None, 45000, 45000)
    caja = esperado(cliente, admin)
    assert (caja["Efectivo"], caja["Nequi"]) == (100000, 45000)


# --- Cancelación (#42, RN-22) ---------------------------------------------------------------


def test_cancelar_sin_decision_devuelve_todo_el_abono(
    cliente, admin, encargo, metodos, caja_abierta
):
    abonar(cliente, admin, encargo, 45000, metodos["Efectivo"])
    r = cancelar(cliente, admin, encargo)
    assert r.status_code == 200, r.text
    e = r.json()
    assert (e["estado"], e["decision_cancelacion"]) == ("cancelado", "devuelve_total")
    assert (e["monto_devuelto"], e["monto_retenido"], e["saldo"]) == (45000, 0, 0)
    assert movimientos(cliente, admin) == [
        ("abono", "Efectivo", 45000),
        ("devolucion_abono", "Efectivo", -45000),
    ]
    assert cliente.get(f"{API}/ventas/resumen", headers=admin).json()["ingresos_cancelacion"] == 0


def test_devolucion_parcial_retiene_el_resto_como_ingreso(
    cliente, admin, encargo, metodos, caja_abierta
):
    abonar(cliente, admin, encargo, 45000, metodos["Nequi"])
    sin_motivo = cancelar(
        cliente, admin, encargo, {"decision": "devuelve_parcial", "monto_devuelto": 30000}
    )
    assert sin_motivo.status_code == 422
    r = cancelar(
        cliente,
        admin,
        encargo,
        {
            "decision": "devuelve_parcial",
            "monto_devuelto": 30000,
            "motivo": "Ya se habían comprado los insumos",
            "metodo_pago_id": metodos["Nequi"],
        },
    )
    assert r.status_code == 200, r.text
    e = r.json()
    assert (e["monto_devuelto"], e["monto_retenido"]) == (30000, 15000)
    assert e["motivo_cancelacion"] == "Ya se habían comprado los insumos"
    assert esperado(cliente, admin)["Nequi"] == 15000
    resumen = cliente.get(f"{API}/ventas/resumen", headers=admin).json()
    # Lo retenido es ingreso por cancelación, no venta (RN-22).
    assert (resumen["total"], resumen["ventas"], resumen["ingresos_cancelacion"]) == (0, 0, 15000)


def test_retener_todo_no_mueve_la_caja(cliente, admin, encargo, metodos, caja_abierta, db):
    abonar(cliente, admin, encargo, 45000, metodos["Nequi"])
    # Con la caja ya cerrada: retener no devuelve dinero, así que no necesita caja abierta.
    db.execute(text("UPDATE caja_sesiones SET estado = 'cerrada', cerrada_en = now()"))
    db.commit()
    r = cancelar(cliente, admin, encargo, {"decision": "retiene", "motivo": "No vino a recogerlo"})
    assert r.status_code == 200, r.text
    assert (r.json()["monto_devuelto"], r.json()["monto_retenido"]) == (0, 45000)


def test_devolver_necesita_caja_abierta(cliente, admin, encargo, metodos, caja_abierta, db):
    abonar(cliente, admin, encargo, 45000, metodos["Nequi"])
    db.execute(text("UPDATE caja_sesiones SET estado = 'cerrada', cerrada_en = now()"))
    db.commit()
    r = cancelar(cliente, admin, encargo)
    assert (r.status_code, r.json()["codigo"]) == (409, "CAJA_CERRADA")
    assert ver(cliente, admin, encargo)["estado"] == "pendiente"


@pytest.mark.parametrize("monto", [0, 45000, 50000])
def test_devolucion_parcial_fuera_de_rango(cliente, admin, encargo, metodos, caja_abierta, monto):
    abonar(cliente, admin, encargo, 45000, metodos["Nequi"])
    r = cancelar(
        cliente,
        admin,
        encargo,
        {"decision": "devuelve_parcial", "monto_devuelto": monto, "motivo": "Insumos comprados"},
    )
    assert r.status_code == 422


def test_solo_un_administrador_cancela(cliente, admin, encargo, crear_usuario, login):
    cajero = login(crear_usuario("cajero"))
    assert cancelar(cliente, cajero, encargo).status_code == 403
    assert estado(cliente, cajero, encargo, "en_produccion").status_code == 200
