"""Forma común de todos los reportes: secciones con columnas tipadas.

Una sola forma permite que una misma rutina lo convierta en JSON, Excel o PDF. Los montos
(``pesos``, ``entero``) son ``int``; ``cantidad`` y ``porcentaje`` son ``Decimal`` y viajan como
string (nunca float). Una fila puede traer ``_tipo`` para cambiar el tipo de su columna
``valor`` (el resumen mezcla pesos y conteos).
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

TipoColumna = Literal["texto", "pesos", "cantidad", "porcentaje", "fecha", "entero"]


class Columna(BaseModel):
    clave: str
    titulo: str
    tipo: TipoColumna


class Seccion(BaseModel):
    titulo: str
    columnas: list[Columna]
    filas: list[dict[str, Any]]
    totales: dict[str, Any] | None = None


class Reporte(BaseModel):
    tipo: str
    titulo: str
    sede: str
    desde: date
    hasta: date
    generado_en: datetime
    secciones: list[Seccion]


def col(clave: str, titulo: str, tipo: TipoColumna = "texto") -> Columna:
    return Columna(clave=clave, titulo=titulo, tipo=tipo)


def seccion(
    titulo: str, columnas: list[Columna], filas: list[dict[str, Any]], sumar: tuple[str, ...] = ()
) -> Seccion:
    """Sección con totales al pie de las columnas indicadas (solo si hay filas)."""
    totales = None
    if sumar:
        totales = {c: sum(f.get(c) or 0 for f in filas) for c in sumar}
    return Seccion(titulo=titulo, columnas=columnas, filas=filas, totales=totales)
