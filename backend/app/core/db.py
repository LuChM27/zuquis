"""Conexión a PostgreSQL y sesión por petición.

Regla de transacciones: los servicios nunca hacen commit (solo flush). El router confirma
con ``db.commit()`` antes de responder, así una operación que mueve dinero o inventario se
guarda completa o no se guarda. Si algo falla, la sesión se cierra y PostgreSQL revierte todo.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_config

engine = create_engine(obtener_config().database_url, pool_pre_ping=True)
SesionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def obtener_db() -> Iterator[Session]:
    db = SesionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
