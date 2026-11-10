import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.modules.auditoria.models import Auditoria
from app.modules.auditoria.service import auditar


def _un_registro(db) -> Auditoria:
    auditar(db, None, "prueba", "pruebas", "1", despues={"x": 1})
    db.commit()
    return db.scalar(select(Auditoria).where(Auditoria.entidad == "pruebas"))


@pytest.mark.parametrize(
    "sentencia",
    ["UPDATE auditoria SET accion = 'cambiada'", "DELETE FROM auditoria", "TRUNCATE auditoria"],
)
def test_auditoria_es_de_solo_insercion(db, sentencia):
    _un_registro(db)
    db.begin_nested()
    with pytest.raises(DBAPIError, match="solo inserción"):
        db.execute(text(sentencia))
    db.rollback()


def test_si_la_operacion_falla_no_queda_auditoria(db):
    db.begin_nested()
    auditar(db, None, "prueba", "fallida", "1")
    db.flush()
    db.rollback()
    assert db.scalar(select(Auditoria).where(Auditoria.entidad == "fallida")) is None


def test_solo_el_admin_consulta_la_auditoria(cliente, admin, crear_usuario, login):
    r = cliente.get("/api/v1/auditoria", headers=admin, params={"entidad": "usuarios"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1  # el login del admin
    cajero = login(crear_usuario("cajero"))
    assert cliente.get("/api/v1/auditoria", headers=cajero).status_code == 403
