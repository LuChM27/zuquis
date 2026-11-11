"""Comandos de administración.

python -m app.cli crear-admin --email dueno@zuquis.co --nombre "Nombre"
python -m app.cli sincronizar-permisos
python -m app.cli limpiar-idempotencia
"""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core import permisos
from app.core.db import SesionLocal
from app.core.idempotencia import limpiar_vencidas
from app.core.seguridad import hashear_clave
from app.modules.auth.models import Usuario
from app.modules.auth.service import normalizar_email
from app.modules.configuracion.models import Sede
from app.modules.usuarios.models import Rol, UsuarioRol


def crear_admin(email: str, nombre: str, clave: str | None) -> None:
    clave = clave or getpass.getpass("Contraseña (mínimo 8 caracteres): ")
    if len(clave) < 8:
        sys.exit("La contraseña debe tener al menos 8 caracteres.")
    with SesionLocal() as db:
        permisos.sincronizar(db)
        email = normalizar_email(email)
        if db.scalar(select(Usuario).where(Usuario.email == email)):
            sys.exit(f"Ya existe un usuario con el correo {email}.")
        rol = db.scalar(select(Rol).where(Rol.clave_base == "admin"))
        sedes = list(db.scalars(select(Sede).where(Sede.activa)))
        usuario = Usuario(nombre=nombre, email=email, password_hash=hashear_clave(clave))
        db.add(usuario)
        db.flush()
        for sede in sedes:
            db.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol.id, sede_id=sede.id))
        db.commit()
        print(f"Administrador {email} creado en {len(sedes)} sede(s).")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="comando", required=True)
    admin = sub.add_parser("crear-admin", help="Crea el usuario administrador inicial")
    admin.add_argument("--email", required=True)
    admin.add_argument("--nombre", required=True)
    admin.add_argument("--clave", help="Solo para scripts; si se omite se pide sin mostrarla")
    sub.add_parser("sincronizar-permisos", help="Sincroniza el catálogo de permisos y roles base")
    sub.add_parser("limpiar-idempotencia", help="Borra claves de idempotencia vencidas")
    args = parser.parse_args()

    if args.comando == "crear-admin":
        crear_admin(args.email, args.nombre, args.clave)
    elif args.comando == "sincronizar-permisos":
        with SesionLocal() as db:
            permisos.sincronizar(db)
            db.commit()
        print("Permisos sincronizados.")
    elif args.comando == "limpiar-idempotencia":
        with SesionLocal() as db:
            n = limpiar_vencidas(db)
            db.commit()
        print(f"{n} claves vencidas eliminadas.")


if __name__ == "__main__":
    main()
