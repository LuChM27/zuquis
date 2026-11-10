"""Paginación (?page=&size=) y filtros de fecha (?desde=&hasta=) comunes a todos los listados."""

from dataclasses import dataclass
from datetime import date

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class Pagina[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int


@dataclass
class ParamsPagina:
    page: int = Query(1, ge=1)
    size: int = Query(50, ge=1, le=200)


@dataclass
class RangoFechas:
    desde: date | None = Query(None, description="Fecha inicial ISO (aaaa-mm-dd)")
    hasta: date | None = Query(None, description="Fecha final ISO (aaaa-mm-dd), inclusive")


def paginar(db: Session, consulta: Select, params: ParamsPagina) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(consulta.order_by(None).subquery()))
    filas = db.scalars(consulta.limit(params.size).offset((params.page - 1) * params.size)).all()
    return list(filas), total or 0
