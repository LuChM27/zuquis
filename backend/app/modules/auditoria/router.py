import uuid
from datetime import datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere
from app.modules.auditoria.models import Auditoria
from app.shared.fechas import zona
from app.shared.paginacion import Pagina, ParamsPagina, RangoFechas, paginar

router = APIRouter(prefix="/auditoria", tags=["Auditoría"])


class AuditoriaSalida(BaseModel):
    id: uuid.UUID
    fecha: datetime
    usuario_id: uuid.UUID | None
    sede_id: uuid.UUID | None
    accion: str
    entidad: str
    entidad_id: str | None
    antes: dict[str, Any] | None
    despues: dict[str, Any] | None
    ip: str | None


@router.get("", response_model=Pagina[AuditoriaSalida])
def listar(
    entidad: str | None = Query(None),
    entidad_id: str | None = Query(None),
    usuario_id: uuid.UUID | None = Query(None),
    rango: RangoFechas = Depends(),
    pagina: ParamsPagina = Depends(),
    _: Contexto = Depends(requiere("auditoria.ver")),
    db: Session = Depends(obtener_db),
):
    consulta = select(Auditoria).order_by(Auditoria.fecha.desc())
    if entidad:
        consulta = consulta.where(Auditoria.entidad == entidad)
    if entidad_id:
        consulta = consulta.where(Auditoria.entidad_id == entidad_id)
    if usuario_id:
        consulta = consulta.where(Auditoria.usuario_id == usuario_id)
    # Las fechas del filtro son días calendario en hora de Colombia.
    if rango.desde:
        consulta = consulta.where(
            Auditoria.fecha >= datetime.combine(rango.desde, time.min, zona())
        )
    if rango.hasta:
        consulta = consulta.where(
            Auditoria.fecha < datetime.combine(rango.hasta + timedelta(days=1), time.min, zona())
        )
    items, total = paginar(db, consulta, pagina)
    return Pagina(items=items, total=total, page=pagina.page, size=pagina.size)
