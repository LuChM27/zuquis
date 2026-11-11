from datetime import timedelta

from sqlalchemy import select

from app.modules.auditoria.models import Auditoria
from app.modules.auth.models import SesionRefresh
from app.modules.configuracion.models import Sede
from app.shared.fechas import ahora
from tests.conftest import CLAVE, SEDE_PRINCIPAL

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"


def test_login_correcto_pone_refresh_en_cookie_httponly(cliente, crear_usuario):
    usuario = crear_usuario("cajero")
    r = cliente.post(LOGIN, json={"email": usuario.email.upper(), "password": CLAVE})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["access_token"]
    assert cuerpo["sede"]["id"] == str(SEDE_PRINCIPAL)
    assert "refresh" not in str(cuerpo).lower().replace("refresh_", "")
    cookie = r.headers["set-cookie"]
    assert "zuquis_refresh=" in cookie
    assert "HttpOnly" in cookie
    assert "samesite=strict" in cookie.lower()
    assert "Path=/api/v1/auth" in cookie


def test_login_incorrecto(cliente, crear_usuario):
    usuario = crear_usuario("cajero")
    r = cliente.post(LOGIN, json={"email": usuario.email, "password": "otra-clave"})
    assert r.status_code == 401
    assert r.json()["codigo"] == "CREDENCIALES_INVALIDAS"
    r = cliente.post(LOGIN, json={"email": "nadie@zuquis.test", "password": "x"})
    assert r.status_code == 401
    assert r.json()["codigo"] == "CREDENCIALES_INVALIDAS"


def test_bloqueo_al_quinto_intento_fallido(cliente, crear_usuario, db):
    usuario = crear_usuario("cajero")
    for _ in range(5):
        r = cliente.post(LOGIN, json={"email": usuario.email, "password": "mala"})
        assert r.status_code == 401
    r = cliente.post(LOGIN, json={"email": usuario.email, "password": CLAVE})
    assert r.status_code == 423
    assert r.json()["codigo"] == "USUARIO_BLOQUEADO"
    fallidos = db.scalars(
        select(Auditoria).where(
            Auditoria.accion == "login_fallido", Auditoria.usuario_id == usuario.id
        )
    ).all()
    assert len(fallidos) == 5


def test_login_exitoso_reinicia_intentos(cliente, crear_usuario, db):
    usuario = crear_usuario("cajero")
    for _ in range(4):
        cliente.post(LOGIN, json={"email": usuario.email, "password": "mala"})
    assert cliente.post(LOGIN, json={"email": usuario.email, "password": CLAVE}).status_code == 200
    db.refresh(usuario)
    assert usuario.intentos_fallidos == 0


def test_limite_de_peticiones_en_login(cliente):
    codigos = [
        cliente.post(LOGIN, json={"email": "nadie@zuquis.test", "password": "x"}).status_code
        for _ in range(21)
    ]
    assert codigos[-1] == 429


def test_refresh_rota_el_token(cliente, crear_usuario, db):
    usuario = crear_usuario("cajero")
    cliente.post(LOGIN, json={"email": usuario.email, "password": CLAVE})
    viejo = cliente.cookies.get("zuquis_refresh")
    r = cliente.post(REFRESH)
    assert r.status_code == 200
    nuevo = cliente.cookies.get("zuquis_refresh")
    assert nuevo and nuevo != viejo
    assert (
        cliente.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}
        ).status_code
        == 200
    )


def test_reusar_refresh_rotado_cierra_toda_la_sesion(cliente, crear_usuario, db):
    usuario = crear_usuario("cajero")
    cliente.post(LOGIN, json={"email": usuario.email, "password": CLAVE})
    robado = cliente.cookies.get("zuquis_refresh")
    assert cliente.post(REFRESH).status_code == 200
    legitimo = cliente.cookies.get("zuquis_refresh")

    # Pasada la ventana de gracia, alguien usa el token viejo.
    for sesion in db.scalars(select(SesionRefresh).where(SesionRefresh.revocado_en.is_not(None))):
        sesion.revocado_en = ahora() - timedelta(minutes=1)
    db.commit()
    cliente.cookies.set("zuquis_refresh", robado, path="/api/v1/auth")
    r = cliente.post(REFRESH)
    assert r.status_code == 401
    assert r.json()["codigo"] == "REFRESH_REUTILIZADO"

    # El token legítimo también quedó revocado.
    cliente.cookies.set("zuquis_refresh", legitimo, path="/api/v1/auth")
    assert cliente.post(REFRESH).status_code == 401


def test_logout_revoca_el_refresh(cliente, crear_usuario):
    usuario = crear_usuario("cajero")
    cliente.post(LOGIN, json={"email": usuario.email, "password": CLAVE})
    token = cliente.cookies.get("zuquis_refresh")
    assert cliente.post("/api/v1/auth/logout").status_code == 204
    cliente.cookies.set("zuquis_refresh", token, path="/api/v1/auth")
    r = cliente.post(REFRESH)
    assert r.status_code == 401


def test_me_devuelve_permisos_efectivos(cliente, crear_usuario, login):
    headers = login(crear_usuario("cajero"))
    r = cliente.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
    cuerpo = r.json()
    assert "ventas.crear" in cuerpo["permisos"]
    assert "ventas.anular" not in cuerpo["permisos"]
    assert cuerpo["roles"] == ["Cajero / Vendedor"]


def test_token_invalido(cliente):
    r = cliente.get("/api/v1/auth/me", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401
    assert r.json()["codigo"] == "TOKEN_INVALIDO"


def test_con_varias_sedes_hay_que_elegir(cliente, crear_usuario, db):
    otra = Sede(nombre="Sede Norte")
    db.add(otra)
    db.commit()
    usuario = crear_usuario("cajero")
    crear_usuario  # noqa: B018
    from app.modules.usuarios.models import UsuarioRol
    from tests.conftest import rol_base

    db.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol_base(db, "admin").id, sede_id=otra.id))
    db.commit()

    r = cliente.post(LOGIN, json={"email": usuario.email, "password": CLAVE})
    assert r.status_code == 409
    assert r.json()["codigo"] == "SEDE_REQUERIDA"
    assert len(r.json()["detalle"]["sedes"]) == 2

    r = cliente.post(
        LOGIN, json={"email": usuario.email, "password": CLAVE, "sede_id": str(otra.id)}
    )
    assert r.status_code == 200
    me = cliente.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}
    ).json()
    # En la sede Norte es admin; en la principal solo cajero.
    assert "ventas.anular" in me["permisos"]


def test_usuario_inactivo_no_entra(cliente, crear_usuario, db):
    usuario = crear_usuario("cajero")
    usuario.activo = False
    db.commit()
    r = cliente.post(LOGIN, json={"email": usuario.email, "password": CLAVE})
    assert r.status_code == 401


def test_bloqueado_con_clave_mala_responde_igual_que_correo_inexistente(cliente, crear_usuario):
    """El bloqueo no revela qué correos existen: solo quien sabe la contraseña ve el 423."""
    usuario = crear_usuario("cajero")
    for _ in range(5):
        cliente.post(LOGIN, json={"email": usuario.email, "password": "mala"})
    con_clave_mala = cliente.post(LOGIN, json={"email": usuario.email, "password": "mala"})
    inexistente = cliente.post(LOGIN, json={"email": "nadie@zuquis.test", "password": "mala"})
    assert con_clave_mala.status_code == inexistente.status_code == 401
    assert con_clave_mala.json() == inexistente.json()
    assert cliente.post(LOGIN, json={"email": usuario.email, "password": CLAVE}).status_code == 423


def test_usuario_con_roles_inactivos_no_entra_ni_renueva(cliente, crear_usuario, admin, db):
    from tests.conftest import rol_base

    usuario = crear_usuario("contador")
    r = cliente.post(LOGIN, json={"email": usuario.email, "password": CLAVE})
    assert r.status_code == 200
    contador = rol_base(db, "contador")
    assert (
        cliente.patch(
            f"/api/v1/roles/{contador.id}", headers=admin, json={"activo": False}
        ).status_code
        == 409  # rol base con usuarios: no se desactiva
    )
    # Se reemplaza por un rol propio y luego se desactiva ese rol.
    rol = cliente.post(
        "/api/v1/roles", headers=admin, json={"nombre": "Temporal", "permisos": ["reportes.ver"]}
    ).json()
    cliente.patch(
        f"/api/v1/usuarios/{usuario.id}",
        headers=admin,
        json={"roles": [{"rol_id": rol["id"], "sede_id": str(SEDE_PRINCIPAL)}]},
    )
    assert (
        cliente.patch(
            f"/api/v1/roles/{rol['id']}", headers=admin, json={"activo": False}
        ).status_code
        == 200
    )

    r = cliente.post(LOGIN, json={"email": usuario.email, "password": CLAVE})
    assert r.status_code == 401
    assert r.json()["codigo"] == "SIN_ROLES"
