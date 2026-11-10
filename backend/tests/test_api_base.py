from fastapi import Depends
from fastapi.routing import APIRoute
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.modules.configuracion.models import Sede
from app.shared.errores import ErrorNegocio

RUTAS_PUBLICAS = {
    "/api/v1/salud",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
}


def test_salud(cliente):
    r = cliente.get("/api/v1/salud")
    assert r.status_code == 200
    assert r.json() == {"api": "ok", "db": "ok"}


def test_formato_de_error_404(cliente):
    r = cliente.get("/api/v1/no-existe")
    assert r.status_code == 404
    assert r.json() == {
        "codigo": "NO_ENCONTRADO",
        "mensaje": "El recurso no existe.",
        "detalle": {},
    }


def test_formato_de_error_validacion(cliente):
    r = cliente.post("/api/v1/auth/login", json={"email": "x"})
    assert r.status_code == 422
    cuerpo = r.json()
    assert cuerpo["codigo"] == "VALIDACION"
    assert {e["campo"] for e in cuerpo["detalle"]["errores"]} >= {"email", "password"}


def test_ninguna_ruta_protegida_responde_sin_token(app, cliente):
    for ruta in app.routes:
        if not isinstance(ruta, APIRoute) or ruta.path in RUTAS_PUBLICAS:
            continue
        for metodo in ruta.methods - {"HEAD", "OPTIONS"}:
            url = ruta.path.replace("{", "").replace("}", "")
            r = cliente.request(metodo, url)
            assert r.status_code == 401, f"{metodo} {ruta.path} respondió {r.status_code} sin token"
            assert r.json()["codigo"] == "NO_AUTENTICADO"


def test_error_a_mitad_de_operacion_revierte_todo(app, cliente, db):
    """Una excepción después de escribir no deja nada guardado (una transacción por operación)."""

    @app.post("/api/v1/_prueba/falla")
    def falla(sesion: Session = Depends(obtener_db)):
        sesion.add(Sede(nombre="Sede fantasma"))
        sesion.flush()
        raise ErrorNegocio("FALLA_A_PROPOSITO", "Falla a propósito.")

    r = cliente.post("/api/v1/_prueba/falla")
    assert r.status_code == 400
    assert r.json()["codigo"] == "FALLA_A_PROPOSITO"
    assert db.scalar(select(Sede).where(Sede.nombre == "Sede fantasma")) is None
