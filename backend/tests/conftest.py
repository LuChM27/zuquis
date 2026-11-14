"""Pruebas contra PostgreSQL real (nunca SQLite).

Cada prueba corre dentro de una transacción que se revierte al final: los ``db.commit()`` de
los routers solo liberan un savepoint. La base de pruebas se recrea con las migraciones de
Alembic al inicio de la sesión, así que las migraciones también quedan probadas.
"""

import os
import uuid
from collections.abc import Iterator

from sqlalchemy.engine import make_url  # noqa: E402

# Las pruebas borran y recrean el esquema: SIEMPRE van contra la base de pruebas, aunque el
# entorno traiga DATABASE_URL (dentro del contenedor de la API apunta a la base real). Una
# base cuyo nombre no termine en "_test" se rechaza antes de tocar nada.
URL_PRUEBAS = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://zuquis:zuquis@127.0.0.1:5433/zuquis_test"
)
if not (make_url(URL_PRUEBAS).database or "").endswith("_test"):
    raise SystemExit(
        f"Las pruebas solo corren contra una base terminada en _test (TEST_DATABASE_URL="
        f"{make_url(URL_PRUEBAS).render_as_string(hide_password=True)})."
    )
os.environ["DATABASE_URL"] = URL_PRUEBAS
os.environ["COOKIE_SECURE"] = "false"
os.environ.setdefault("JWT_SECRET", "clave-de-pruebas-de-al-menos-32-bytes-de-largo")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core import limite, permisos  # noqa: E402
from app.core.db import engine, obtener_db  # noqa: E402
from app.core.seguridad import hashear_clave  # noqa: E402
from app.main import crear_app  # noqa: E402
from app.modules.archivos import service as archivos_service  # noqa: E402
from app.modules.auth.models import Usuario  # noqa: E402
from app.modules.usuarios.models import Rol, UsuarioRol  # noqa: E402

# Escenarios compartidos entre archivos de pruebas.
pytest_plugins = ["tests.fixtures_ventas"]

SEDE_PRINCIPAL = uuid.UUID("00000000-0000-0000-0000-000000000001")
CLAVE = "clave-segura-123"


@pytest.fixture(scope="session", autouse=True)
def esquema() -> None:
    # Segunda barrera: el motor ya creado debe apuntar a la base de pruebas.
    assert (engine.url.database or "").endswith("_test"), engine.url.database
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def db() -> Iterator[Session]:
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(
        bind=conexion, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    permisos.sincronizar(sesion)
    sesion.commit()  # solo libera el savepoint; la transacción externa se revierte al final
    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()


@pytest.fixture
def app(db: Session, tmp_path):
    aplicacion = crear_app(sincronizar_al_iniciar=False)

    def _db() -> Iterator[Session]:
        # Igual que obtener_db: lo que no se confirmó se revierte al terminar la petición.
        try:
            yield db
        finally:
            db.rollback()

    aplicacion.dependency_overrides[obtener_db] = _db
    aplicacion.dependency_overrides[archivos_service.almacen] = lambda: (
        archivos_service.AlmacenLocal(str(tmp_path))
    )
    limite.reiniciar()
    return aplicacion


@pytest.fixture
def cliente(app) -> TestClient:
    return TestClient(app)


def rol_base(db: Session, clave_base: str) -> Rol:
    return db.query(Rol).filter(Rol.clave_base == clave_base).one()


@pytest.fixture
def crear_usuario(db: Session):
    """crear_usuario("cajero") crea un usuario con ese rol base en la sede principal."""

    def _crear(
        *claves_rol: str,
        email: str | None = None,
        sede_id: uuid.UUID = SEDE_PRINCIPAL,
        nombre: str = "Prueba",
    ) -> Usuario:
        usuario = Usuario(
            nombre=nombre,
            email=email or f"{uuid.uuid4().hex[:8]}@zuquis.test",
            password_hash=hashear_clave(CLAVE),
        )
        db.add(usuario)
        db.flush()
        for clave in claves_rol:
            db.add(
                UsuarioRol(usuario_id=usuario.id, rol_id=rol_base(db, clave).id, sede_id=sede_id)
            )
        db.commit()
        return usuario

    return _crear


@pytest.fixture
def login(cliente: TestClient):
    """login(usuario) → encabezados con el token de acceso."""

    def _login(usuario: Usuario, sede_id: uuid.UUID | None = None) -> dict[str, str]:
        cuerpo = {"email": usuario.email, "password": CLAVE}
        if sede_id:
            cuerpo["sede_id"] = str(sede_id)
        r = cliente.post("/api/v1/auth/login", json=cuerpo)
        assert r.status_code == 200, r.json()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _login


@pytest.fixture
def admin(crear_usuario, login) -> dict[str, str]:
    return login(crear_usuario("admin"))
