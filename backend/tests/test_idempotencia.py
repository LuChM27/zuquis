"""Idempotency-Key: un reintento del POS no duplica la operación (sección 9)."""

import threading
import uuid

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.db import SesionLocal, obtener_db
from app.core.deps import Contexto, obtener_contexto
from app.core.idempotencia import Idempotencia, idempotencia
from app.core.idempotencia_models import Idempotencia as Registro
from app.core.seguridad import hashear_clave
from app.main import crear_app
from app.modules.auditoria.service import auditar
from app.modules.auth.models import SesionRefresh, Usuario
from app.modules.usuarios.models import Rol, UsuarioRol
from tests.conftest import CLAVE, SEDE_PRINCIPAL


class Entrada(BaseModel):
    valor: int


def _montar_ruta(app, retraso: threading.Event | None = None):
    """Ruta de prueba que 'mueve dinero': deja un registro de auditoría por ejecución."""

    @app.post("/api/v1/_prueba/operacion", status_code=201)
    def operacion(
        datos: Entrada,
        ctx: Contexto = Depends(obtener_contexto),
        idem: Idempotencia = Depends(idempotencia(requerida=True)),
        db: Session = Depends(obtener_db),
    ):
        if (previa := idem.iniciar(db, ctx)) is not None:
            return previa
        auditar(db, ctx, "operacion", "pruebas_idem", str(datos.valor))
        if retraso is not None:
            retraso.wait(timeout=5)
        salida = {"ejecutada": True, "valor": datos.valor}
        idem.guardar(db, 201, salida)
        db.commit()
        return salida


def _ejecuciones(db, valor: str = "7") -> int:
    from app.modules.auditoria.models import Auditoria

    return db.scalar(
        select(func.count())
        .select_from(Auditoria)
        .where(Auditoria.entidad == "pruebas_idem", Auditoria.entidad_id == valor)
    )


def test_misma_clave_y_mismo_cuerpo_se_ejecuta_una_vez(app, cliente, admin, db):
    _montar_ruta(app)
    headers = admin | {"Idempotency-Key": "venta-123"}
    r1 = cliente.post("/api/v1/_prueba/operacion", headers=headers, json={"valor": 7})
    r2 = cliente.post("/api/v1/_prueba/operacion", headers=headers, json={"valor": 7})
    assert r1.status_code == r2.status_code == 201
    assert r1.json() == r2.json()
    assert r2.headers.get("Idempotent-Replayed") == "true"
    assert _ejecuciones(db) == 1


def test_misma_clave_con_otro_cuerpo_es_conflicto(app, cliente, admin):
    _montar_ruta(app)
    headers = admin | {"Idempotency-Key": "venta-456"}
    cliente.post("/api/v1/_prueba/operacion", headers=headers, json={"valor": 7})
    r = cliente.post("/api/v1/_prueba/operacion", headers=headers, json={"valor": 8})
    assert r.status_code == 409
    assert r.json()["codigo"] == "IDEMPOTENCIA_CONFLICTO"


def test_clave_obligatoria(app, cliente, admin):
    _montar_ruta(app)
    r = cliente.post("/api/v1/_prueba/operacion", headers=admin, json={"valor": 7})
    assert r.status_code == 400
    assert r.json()["codigo"] == "IDEMPOTENCIA_REQUERIDA"


@pytest.fixture
def usuario_real():
    """Usuario confirmado de verdad en la base (la prueba de concurrencia usa dos conexiones)."""
    with SesionLocal() as s:
        from app.core import permisos

        permisos.sincronizar(s)
        usuario = Usuario(
            nombre="Concurrencia",
            email=f"{uuid.uuid4().hex[:8]}@zuquis.test",
            password_hash=hashear_clave(CLAVE),
        )
        s.add(usuario)
        s.flush()
        rol = s.scalar(select(Rol).where(Rol.clave_base == "admin"))
        s.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id, sede_id=SEDE_PRINCIPAL))
        s.commit()
        yield usuario
        from app.modules.auditoria.models import Auditoria

        s.execute(delete(Registro).where(Registro.usuario_id == usuario.id))
        s.execute(delete(SesionRefresh).where(SesionRefresh.usuario_id == usuario.id))
        s.execute(delete(UsuarioRol).where(UsuarioRol.usuario_id == usuario.id))
        s.commit()
        # La auditoría es de solo inserción: sus filas quedan, apuntando a un usuario que se
        # desactiva en lugar de borrarse.
        s.get(Usuario, usuario.id).activo = False
        s.commit()
        _ = Auditoria


def test_dos_peticiones_simultaneas_ejecutan_una_sola_vez(usuario_real):
    """Sin overrides de base de datos: cada petición usa su propia conexión real."""
    app = crear_app(sincronizar_al_iniciar=False)
    liberar = threading.Event()
    _montar_ruta(app, retraso=liberar)
    cliente = TestClient(app)
    token = cliente.post(
        "/api/v1/auth/login", json={"email": usuario_real.email, "password": CLAVE}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": f"concurrente-{uuid.uuid4()}"}
    valor = 900 + uuid.uuid4().int % 1000
    respuestas = []

    def enviar():
        respuestas.append(
            cliente.post("/api/v1/_prueba/operacion", headers=headers, json={"valor": valor})
        )

    hilos = [threading.Thread(target=enviar) for _ in range(2)]
    for h in hilos:
        h.start()
    threading.Timer(0.5, liberar.set).start()
    for h in hilos:
        h.join(timeout=10)

    assert [r.status_code for r in respuestas] == [201, 201]
    with SesionLocal() as s:
        assert _ejecuciones(s, str(valor)) == 1


def test_clave_vencida_con_reintentos_simultaneos_ejecuta_una_sola_vez(usuario_real):
    """Dos reintentos a la vez con una clave vencida: uno la toma, el otro reproduce la respuesta
    (antes chocaban en el índice único y uno devolvía 500)."""
    from datetime import timedelta

    from app.shared.fechas import ahora

    clave = f"vencida-{uuid.uuid4()}"
    with SesionLocal() as s:
        s.add(
            Registro(
                usuario_id=usuario_real.id,
                clave=clave,
                ruta="POST /api/v1/_prueba/operacion",
                hash_cuerpo="viejo",
                expira_en=ahora() - timedelta(hours=1),
                estado_http=201,
                respuesta={"viejo": True},
            )
        )
        s.commit()

    app = crear_app(sincronizar_al_iniciar=False)
    liberar = threading.Event()
    _montar_ruta(app, retraso=liberar)
    cliente = TestClient(app)
    token = cliente.post(
        "/api/v1/auth/login", json={"email": usuario_real.email, "password": CLAVE}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": clave}
    valor = 2000 + uuid.uuid4().int % 1000
    respuestas = []

    def enviar():
        respuestas.append(
            cliente.post("/api/v1/_prueba/operacion", headers=headers, json={"valor": valor})
        )

    hilos = [threading.Thread(target=enviar) for _ in range(2)]
    for h in hilos:
        h.start()
    threading.Timer(0.5, liberar.set).start()
    for h in hilos:
        h.join(timeout=10)

    assert [r.status_code for r in respuestas] == [201, 201]
    assert all(r.json() == {"ejecutada": True, "valor": valor} for r in respuestas)
    with SesionLocal() as s:
        assert _ejecuciones(s, str(valor)) == 1
