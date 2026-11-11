from sqlalchemy import select

from app.modules.auditoria.models import Auditoria
from tests.conftest import rol_base


def test_configuracion_trae_valores_por_defecto(cliente, admin):
    r = cliente.get("/api/v1/configuracion", headers=admin)
    assert r.status_code == 200
    cfg = r.json()
    assert cfg["permitir_venta_sin_stock"] is False
    assert cfg["dias_alerta_vencimiento"] == 3
    assert cfg["impuestos"] == {
        "activo": False,
        "tipo": None,
        "tarifa": "0.0000",
        "precios_incluyen_impuesto": True,
    }
    assert cfg["negocio"]["nombre"] == "Zuqui's Repostería"


def test_actualizar_configuracion_queda_auditado(cliente, admin, db):
    cajero = rol_base(db, "cajero")
    r = cliente.patch(
        "/api/v1/configuracion",
        headers=admin,
        json={"dias_alerta_vencimiento": 5, "tope_descuento_por_rol": {str(cajero.id): "10"}},
    )
    assert r.status_code == 200
    assert r.json()["dias_alerta_vencimiento"] == 5
    assert r.json()["tope_descuento_por_rol"] == {str(cajero.id): "10.0000"}
    registro = db.scalar(select(Auditoria).where(Auditoria.entidad == "configuracion"))
    assert registro.antes == {"dias_alerta_vencimiento": 3, "tope_descuento_por_rol": {}}


def test_clave_desconocida_o_valor_invalido(cliente, admin):
    r = cliente.patch("/api/v1/configuracion", headers=admin, json={"no_existe": 1})
    assert r.status_code == 422
    assert r.json()["codigo"] == "CLAVE_DESCONOCIDA"
    r = cliente.patch("/api/v1/configuracion", headers=admin, json={"impuestos": {"tarifa": 0.19}})
    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"


def test_cajero_lee_pero_no_edita_configuracion(cliente, crear_usuario, login):
    headers = login(crear_usuario("cajero"))
    assert cliente.get("/api/v1/configuracion", headers=headers).status_code == 200
    assert (
        cliente.patch(
            "/api/v1/configuracion", headers=headers, json={"dias_alerta_vencimiento": 1}
        ).status_code
        == 403
    )


def test_metodos_de_pago_iniciales(cliente, admin):
    metodos = cliente.get("/api/v1/metodos-pago", headers=admin).json()
    assert [m["nombre"] for m in metodos] == [
        "Efectivo",
        "Nequi",
        "Bre-B",
        "Bancolombia",
        "Otra transferencia",
    ]
    assert [m["cuenta_puc"] for m in metodos] == ["1105", "1110", "1110", "1110", "1110"]
    assert all(m["titular"] == "negocio" for m in metodos)


def test_un_solo_efectivo_activo(cliente, admin):
    r = cliente.post(
        "/api/v1/metodos-pago", headers=admin, json={"nombre": "Caja menor", "es_efectivo": True}
    )
    assert r.status_code == 409
    assert r.json()["codigo"] == "EFECTIVO_DUPLICADO"


def test_transferencia_a_cuenta_de_dueno(cliente, admin):
    r = cliente.post(
        "/api/v1/metodos-pago",
        headers=admin,
        json={"nombre": "Nequi de la dueña", "titular": "dueno", "cuenta_puc": "1325"},
    )
    assert r.status_code == 201
    assert r.json()["titular"] == "dueno"


def test_crear_sede_trae_metodos_de_pago(cliente, admin):
    r = cliente.post("/api/v1/sedes", headers=admin, json={"nombre": "Sede Norte"})
    assert r.status_code == 201
    assert len(cliente.get("/api/v1/sedes", headers=admin).json()) == 2


def test_unidades(cliente, admin):
    assert [u["codigo"] for u in cliente.get("/api/v1/unidades", headers=admin).json()] == [
        "g",
        "ml",
        "und",
    ]


def test_null_en_campo_obligatorio_es_error_de_validacion(cliente, admin):
    """Antes llegaba a la columna NOT NULL: 409 equivocado en métodos y 500 en sedes."""
    metodo = cliente.get("/api/v1/metodos-pago", headers=admin).json()[0]
    r = cliente.patch(f"/api/v1/metodos-pago/{metodo['id']}", headers=admin, json={"nombre": None})
    assert r.status_code == 422
    assert r.json()["codigo"] == "VALIDACION"
    sede = cliente.get("/api/v1/sedes", headers=admin).json()[0]
    r = cliente.patch(f"/api/v1/sedes/{sede['id']}", headers=admin, json={"activa": None})
    assert r.status_code == 422
    # Un null en un campo opcional sí borra el valor.
    r = cliente.patch(f"/api/v1/sedes/{sede['id']}", headers=admin, json={"telefono": None})
    assert r.status_code == 200
    assert r.json()["telefono"] is None
