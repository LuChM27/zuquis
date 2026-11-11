from sqlalchemy import select

from app.modules.auditoria.models import Auditoria
from app.modules.usuarios.models import UsuarioRol
from tests.conftest import SEDE_PRINCIPAL, rol_base


def test_union_de_permisos_de_dos_roles(cliente, crear_usuario, login):
    headers = login(crear_usuario("cajero", "produccion"))
    permisos = set(cliente.get("/api/v1/auth/me", headers=headers).json()["permisos"])
    assert {"ventas.crear", "produccion.crear", "recetas.editar"} <= permisos
    assert "ventas.anular" not in permisos


def test_sin_permiso_responde_403(cliente, crear_usuario, login):
    headers = login(crear_usuario("cajero"))
    r = cliente.get("/api/v1/usuarios", headers=headers)
    assert r.status_code == 403
    assert r.json() == {
        "codigo": "SIN_PERMISO",
        "mensaje": "No tienes permiso para hacer esta operación.",
        "detalle": {"permiso": "usuarios.gestionar"},
    }


def test_roles_base_por_defecto(cliente, admin):
    roles = {r["nombre"]: r for r in cliente.get("/api/v1/roles", headers=admin).json()}
    assert set(roles) >= {"Dueño / Admin", "Cajero / Vendedor", "Producción / Cocina", "Contador"}
    assert all(roles[n]["es_base"] for n in roles if n != "x")
    assert "inventario.ajustar" not in roles["Producción / Cocina"]["permisos"]
    assert "reportes.exportar" in roles["Contador"]["permisos"]


def test_crear_editar_y_duplicar_rol_queda_auditado(cliente, admin, db):
    r = cliente.post(
        "/api/v1/roles", headers=admin, json={"nombre": "Mesero", "permisos": ["ventas.crear"]}
    )
    assert r.status_code == 201
    rol_id = r.json()["id"]
    r = cliente.patch(
        f"/api/v1/roles/{rol_id}",
        headers=admin,
        json={"permisos": ["ventas.crear", "clientes.gestionar"]},
    )
    assert r.json()["permisos"] == ["clientes.gestionar", "ventas.crear"]
    r = cliente.post(f"/api/v1/roles/{rol_id}/duplicar", headers=admin)
    assert r.status_code == 201
    assert r.json()["nombre"] == "Mesero (copia)"

    cambio = db.scalar(
        select(Auditoria).where(
            Auditoria.entidad == "roles",
            Auditoria.entidad_id == rol_id,
            Auditoria.accion == "editar",
        )
    )
    assert cambio.antes["permisos"] == ["ventas.crear"]
    assert cambio.despues["permisos"] == ["clientes.gestionar", "ventas.crear"]


def test_permiso_desconocido(cliente, admin):
    r = cliente.post(
        "/api/v1/roles", headers=admin, json={"nombre": "Raro", "permisos": ["no.existe"]}
    )
    assert r.status_code == 422
    assert r.json()["codigo"] == "PERMISO_DESCONOCIDO"


def test_rol_base_con_usuarios_no_se_desactiva_ni_elimina(cliente, admin, crear_usuario, db):
    crear_usuario("cajero")
    cajero = rol_base(db, "cajero")
    r = cliente.patch(f"/api/v1/roles/{cajero.id}", headers=admin, json={"activo": False})
    assert r.status_code == 409
    assert r.json()["codigo"] == "ROL_BASE_CON_USUARIOS"
    r = cliente.delete(f"/api/v1/roles/{cajero.id}", headers=admin)
    assert r.status_code == 409
    assert r.json()["codigo"] == "ROL_CON_USUARIOS"


def test_rol_sin_usuarios_se_elimina(cliente, admin):
    rol_id = cliente.post("/api/v1/roles", headers=admin, json={"nombre": "Temporal"}).json()["id"]
    assert cliente.delete(f"/api/v1/roles/{rol_id}", headers=admin).status_code == 204


def test_no_se_puede_quedar_sin_administrador(cliente, admin, db):
    admin_rol = rol_base(db, "admin")
    r = cliente.patch(
        f"/api/v1/roles/{admin_rol.id}", headers=admin, json={"permisos": ["ventas.crear"]}
    )
    assert r.status_code == 409
    assert r.json()["codigo"] == "SIN_ADMINISTRADOR"


def test_crear_usuario_y_asignar_roles_por_sede(cliente, admin, db):
    cajero = rol_base(db, "cajero")
    r = cliente.post(
        "/api/v1/usuarios",
        headers=admin,
        json={
            "nombre": "Ana",
            "email": "Ana@Zuquis.test",
            "password": "una-clave-larga",
            "roles": [{"rol_id": str(cajero.id), "sede_id": str(SEDE_PRINCIPAL)}],
        },
    )
    assert r.status_code == 201
    assert r.json()["email"] == "ana@zuquis.test"
    assert r.json()["roles"][0]["rol_nombre"] == "Cajero / Vendedor"

    r = cliente.post(
        "/api/v1/usuarios",
        headers=admin,
        json={
            "nombre": "Otra Ana",
            "email": "ana@zuquis.test",
            "password": "una-clave-larga",
            "roles": [{"rol_id": str(cajero.id), "sede_id": str(SEDE_PRINCIPAL)}],
        },
    )
    assert r.status_code == 409
    assert r.json()["codigo"] == "EMAIL_DUPLICADO"

    auditoria = db.scalar(
        select(Auditoria).where(Auditoria.entidad == "usuarios", Auditoria.accion == "crear")
    )
    assert "password" not in str(auditoria.despues)


def test_desactivar_usuario_le_cierra_la_sesion(cliente, admin, crear_usuario, login):
    usuario = crear_usuario("cajero")
    headers = login(usuario)
    r = cliente.patch(f"/api/v1/usuarios/{usuario.id}", headers=admin, json={"activo": False})
    assert r.status_code == 200
    assert cliente.get("/api/v1/auth/me", headers=headers).json()["codigo"] == "USUARIO_INACTIVO"


def test_cambiar_roles_reemplaza_asignaciones(cliente, admin, crear_usuario, db):
    usuario = crear_usuario("cajero")
    contador = rol_base(db, "contador")
    r = cliente.patch(
        f"/api/v1/usuarios/{usuario.id}",
        headers=admin,
        json={"roles": [{"rol_id": str(contador.id), "sede_id": str(SEDE_PRINCIPAL)}]},
    )
    assert [x["rol_nombre"] for x in r.json()["roles"]] == ["Contador"]
    assert (
        db.scalars(select(UsuarioRol).where(UsuarioRol.usuario_id == usuario.id)).all()[0].rol_id
        == contador.id
    )


def test_eliminar_rol_quita_su_tope_de_descuento(cliente, admin):
    """Antes el id quedaba en la configuración y toda edición de Negocio fallaba con 404."""
    rol_id = cliente.post("/api/v1/roles", headers=admin, json={"nombre": "Temporal"}).json()["id"]
    r = cliente.patch(
        "/api/v1/configuracion", headers=admin, json={"tope_descuento_por_rol": {rol_id: "10"}}
    )
    assert r.status_code == 200
    assert cliente.delete(f"/api/v1/roles/{rol_id}", headers=admin).status_code == 204

    config = cliente.get("/api/v1/configuracion", headers=admin).json()
    assert rol_id not in config["tope_descuento_por_rol"]
    r = cliente.patch(
        "/api/v1/configuracion",
        headers=admin,
        json={
            "tope_descuento_por_rol": config["tope_descuento_por_rol"],
            "dias_alerta_vencimiento": 4,
        },
    )
    assert r.status_code == 200


def test_configuracion_y_usuarios_se_ven_entre_si_lo_necesario(
    cliente, admin, login, crear_usuario, db
):
    """Quien solo administra usuarios necesita las sedes; quien solo edita la configuración
    necesita los roles (para los topes de descuento)."""

    def usuario_con(*permisos):
        rol = cliente.post(
            "/api/v1/roles",
            headers=admin,
            json={"nombre": f"Solo {permisos[0]}", "permisos": list(permisos)},
        ).json()
        u = crear_usuario()
        cliente.patch(
            f"/api/v1/usuarios/{u.id}",
            headers=admin,
            json={"roles": [{"rol_id": rol["id"], "sede_id": str(SEDE_PRINCIPAL)}]},
        )
        return login(u)

    gestor = usuario_con("usuarios.gestionar")
    assert cliente.get("/api/v1/sedes", headers=gestor).status_code == 200
    editor = usuario_con("config.editar")
    assert cliente.get("/api/v1/roles", headers=editor).status_code == 200
    # Ver no da permiso para cambiar.
    assert cliente.post("/api/v1/sedes", headers=gestor, json={"nombre": "Otra"}).status_code == 403
    assert cliente.post("/api/v1/roles", headers=editor, json={"nombre": "Otro"}).status_code == 403
