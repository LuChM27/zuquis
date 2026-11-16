import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.modules.clientes import service
from app.modules.clientes.schemas import ClienteCrear, ClienteEditar, ClienteSalida, Historial
from app.shared.paginacion import Pagina, ParamsPagina

router = APIRouter(tags=["Clientes"])

# Quien vende o toma encargos necesita buscar clientes aunque no los administre.
lector = requiere_alguno("clientes.gestionar", "encargos.crear", "ventas.crear", "reportes.ver")
gestor = requiere("clientes.gestionar")


@router.get("/clientes", response_model=Pagina[ClienteSalida])
def listar_clientes(
    params: ParamsPagina = Depends(),
    q: str | None = Query(None, description="Parte del nombre o del teléfono"),
    incluir_inactivos: bool = Query(False),
    ctx: Contexto = Depends(lector),
    db: Session = Depends(obtener_db),
):
    items, total = service.listar(db, ctx, params, q, incluir_inactivos)
    return Pagina(items=items, total=total, page=params.page, size=params.size)


@router.post("/clientes", response_model=ClienteSalida, status_code=201)
def crear_cliente(
    datos: ClienteCrear, ctx: Contexto = Depends(gestor), db: Session = Depends(obtener_db)
):
    """Si otro cliente ya tiene ese teléfono responde 409 TELEFONO_REPETIDO con sus datos; se
    puede crear de todos modos con `permitir_telefono_repetido`."""
    c = service.crear(db, ctx, datos)
    db.commit()
    return c


@router.patch("/clientes/{cliente_id}", response_model=ClienteSalida)
def editar_cliente(
    cliente_id: uuid.UUID,
    datos: ClienteEditar,
    ctx: Contexto = Depends(gestor),
    db: Session = Depends(obtener_db),
):
    c = service.editar(db, ctx, cliente_id, datos)
    db.commit()
    return c


@router.get("/clientes/{cliente_id}/historial", response_model=Historial)
def historial_cliente(
    cliente_id: uuid.UUID, ctx: Contexto = Depends(lector), db: Session = Depends(obtener_db)
):
    return service.historial(db, ctx, cliente_id)
