"""Guardias del modelo de datos (RNF-01, RNF-05)."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Float, Numeric

import app.models  # noqa: F401 - registra todos los modelos
from app.core.db import engine
from app.core.modelo import Base

# Catálogos globales o tablas técnicas que no pertenecen a una sede.
SIN_SEDE = {
    "producto_modificadores",
    "proveedor_insumos",
    "sedes",
    "usuarios",
    "roles",
    "permisos",
    "rol_permisos",
    "unidades",
    "idempotencia",
}


def test_ninguna_columna_es_float():
    flotantes = [
        f"{tabla.name}.{columna.name}"
        for tabla in Base.metadata.sorted_tables
        for columna in tabla.columns
        if isinstance(columna.type, Float)
        or (isinstance(columna.type, Numeric) and not columna.type.asdecimal)
    ]
    assert flotantes == [], f"Columnas con float prohibidas (RNF-01): {flotantes}"


def test_tablas_operativas_tienen_sede():
    sin_sede = [
        t.name
        for t in Base.metadata.sorted_tables
        if t.name not in SIN_SEDE and "sede_id" not in t.columns
    ]
    assert sin_sede == [], f"Tablas sin sede_id (RNF-05): {sin_sede}"


def test_migraciones_al_dia_con_los_modelos():
    with engine.connect() as conexion:
        diferencias = compare_metadata(MigrationContext.configure(conexion), Base.metadata)
    assert diferencias == [], f"Falta una migración de Alembic: {diferencias}"
