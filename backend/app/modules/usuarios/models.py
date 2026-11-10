import uuid

from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.modelo import Base, ConId, ConTiempos

rol_permisos = Table(
    "rol_permisos",
    Base.metadata,
    Column("rol_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permiso_id", ForeignKey("permisos.id", ondelete="CASCADE"), primary_key=True),
)


class Permiso(Base, ConId):
    """Catálogo fijo definido en código (app/core/permisos.py), sincronizado al iniciar."""

    __tablename__ = "permisos"

    clave: Mapped[str] = mapped_column(String(60), unique=True)
    descripcion: Mapped[str] = mapped_column(String(200))
    modulo: Mapped[str] = mapped_column(String(40))


class Rol(Base, ConId, ConTiempos):
    __tablename__ = "roles"

    nombre: Mapped[str] = mapped_column(String(80), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(200))
    es_base: Mapped[bool] = mapped_column(default=False)
    # Identifica los cuatro roles base aunque el admin les cambie el nombre.
    clave_base: Mapped[str | None] = mapped_column(String(30), unique=True)
    activo: Mapped[bool] = mapped_column(default=True)

    permisos: Mapped[list[Permiso]] = relationship(secondary=rol_permisos, lazy="selectin")


class UsuarioRol(Base, ConId):
    """Rol de un usuario en una sede. Un usuario puede tener roles distintos por sede."""

    __tablename__ = "usuario_roles"
    __table_args__ = (UniqueConstraint("usuario_id", "rol_id", "sede_id"),)

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    rol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"))
    sede_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sedes.id"))

    rol: Mapped[Rol] = relationship(lazy="joined")
