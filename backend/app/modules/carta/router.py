import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, obtener_contexto, requiere, requiere_alguno
from app.modules.carta import service
from app.modules.carta.models import Modificador
from app.modules.carta.schemas import (
    CategoriaCrear,
    CategoriaEditar,
    CategoriaSalida,
    CostoSalida,
    ModificadorCrear,
    ModificadorEditar,
    ModificadorSalida,
    PrecioHistorialSalida,
    ProductoCrear,
    ProductoEditar,
    ProductoSalida,
    RecetaEntrada,
    RecetaSalida,
)
from app.shared.errores import ErrorNegocio, NoEncontrado

router = APIRouter(tags=["Carta y recetas"])

editor_carta = requiere("carta.editar")
editor_recetas = requiere("recetas.editar")
lector_recetas = requiere_alguno(
    "recetas.editar", "carta.editar", "produccion.crear", "inventario.ver"
)


# --- Categorías (lectura para todos: el POS las usa) ----------------------------------------


@router.get("/categorias", response_model=list[CategoriaSalida])
def listar_categorias(
    incluir_inactivas: bool = Query(False),
    ctx: Contexto = Depends(obtener_contexto),
    db: Session = Depends(obtener_db),
):
    return service.listar_categorias(db, ctx, incluir_inactivas)


@router.post("/categorias", response_model=CategoriaSalida, status_code=201)
def crear_categoria(
    datos: CategoriaCrear, ctx: Contexto = Depends(editor_carta), db: Session = Depends(obtener_db)
):
    c = service.crear_categoria(db, ctx, datos)
    db.commit()
    return c


@router.patch("/categorias/{categoria_id}", response_model=CategoriaSalida)
def editar_categoria(
    categoria_id: uuid.UUID,
    datos: CategoriaEditar,
    ctx: Contexto = Depends(editor_carta),
    db: Session = Depends(obtener_db),
):
    c = service.editar_categoria(db, ctx, categoria_id, datos)
    db.commit()
    return c


# --- Adiciones ------------------------------------------------------------------------------


@router.get("/modificadores", response_model=list[ModificadorSalida])
def listar_modificadores(
    incluir_inactivos: bool = Query(False),
    ctx: Contexto = Depends(obtener_contexto),
    db: Session = Depends(obtener_db),
):
    return service.listar_modificadores(db, ctx, incluir_inactivos)


@router.post("/modificadores", response_model=ModificadorSalida, status_code=201)
def crear_modificador(
    datos: ModificadorCrear,
    ctx: Contexto = Depends(editor_carta),
    db: Session = Depends(obtener_db),
):
    m = service.crear_modificador(db, ctx, datos)
    db.commit()
    return service.modificador_salida(db, m)


@router.patch("/modificadores/{modificador_id}", response_model=ModificadorSalida)
def editar_modificador(
    modificador_id: uuid.UUID,
    datos: ModificadorEditar,
    ctx: Contexto = Depends(editor_carta),
    db: Session = Depends(obtener_db),
):
    m = service.editar_modificador(db, ctx, modificador_id, datos)
    db.commit()
    return service.modificador_salida(db, m)


# --- Productos ------------------------------------------------------------------------------


@router.get("/productos", response_model=list[ProductoSalida])
def listar_productos(
    categoria_id: uuid.UUID | None = Query(None),
    tipo: str | None = Query(None, pattern="^(preparado|lote)$"),
    incluir_inactivos: bool = Query(False, description="Para reportes y administración"),
    ctx: Contexto = Depends(obtener_contexto),
    db: Session = Depends(obtener_db),
):
    return service.listar_productos(db, ctx, categoria_id, incluir_inactivos, tipo)


@router.post("/productos", response_model=ProductoSalida, status_code=201)
def crear_producto(
    datos: ProductoCrear, ctx: Contexto = Depends(editor_carta), db: Session = Depends(obtener_db)
):
    p = service.crear_producto(db, ctx, datos)
    db.commit()
    return service.producto_salida(db, ctx, p)


@router.get("/productos/{producto_id}", response_model=ProductoSalida)
def ver_producto(
    producto_id: uuid.UUID,
    ctx: Contexto = Depends(obtener_contexto),
    db: Session = Depends(obtener_db),
):
    return service.producto_salida(db, ctx, service.obtener_producto(db, ctx, producto_id))


@router.patch("/productos/{producto_id}", response_model=ProductoSalida)
def editar_producto(
    producto_id: uuid.UUID,
    datos: ProductoEditar,
    ctx: Contexto = Depends(editor_carta),
    db: Session = Depends(obtener_db),
):
    p = service.editar_producto(db, ctx, producto_id, datos)
    db.commit()
    db.refresh(p)
    return service.producto_salida(db, ctx, p)


@router.get("/productos/{producto_id}/precios", response_model=list[PrecioHistorialSalida])
def historial_precios(
    producto_id: uuid.UUID, ctx: Contexto = Depends(editor_carta), db: Session = Depends(obtener_db)
):
    return service.historial_precios(db, ctx, producto_id)


# --- Recetas de productos -------------------------------------------------------------------


@router.get("/productos/{producto_id}/receta", response_model=RecetaSalida)
def ver_receta(
    producto_id: uuid.UUID,
    ctx: Contexto = Depends(lector_recetas),
    db: Session = Depends(obtener_db),
):
    service.obtener_producto(db, ctx, producto_id)
    receta = service.receta_vigente(db, producto_id=producto_id)
    if receta is None:
        raise NoEncontrado("la receta del producto", producto_id)
    return service.receta_salida(db, receta)


@router.put("/productos/{producto_id}/receta", response_model=RecetaSalida)
def guardar_receta(
    producto_id: uuid.UUID,
    datos: RecetaEntrada,
    ctx: Contexto = Depends(editor_recetas),
    db: Session = Depends(obtener_db),
):
    service.obtener_producto(db, ctx, producto_id)
    receta = service.guardar_receta(db, ctx, datos, producto_id=producto_id)
    db.commit()
    return service.receta_salida(db, receta)


@router.get("/productos/{producto_id}/receta/versiones", response_model=list[RecetaSalida])
def versiones_receta(
    producto_id: uuid.UUID,
    ctx: Contexto = Depends(lector_recetas),
    db: Session = Depends(obtener_db),
):
    service.obtener_producto(db, ctx, producto_id)
    return service.versiones(db, producto_id=producto_id)


@router.get("/productos/{producto_id}/costo", response_model=CostoSalida)
def costo_producto(
    producto_id: uuid.UUID,
    ctx: Contexto = Depends(lector_recetas),
    db: Session = Depends(obtener_db),
):
    producto = service.obtener_producto(db, ctx, producto_id)
    receta = service.receta_vigente(db, producto_id=producto_id)
    if receta is None:
        raise ErrorNegocio("SIN_RECETA", "Este producto no tiene receta.", status=404)
    return service.costo_teorico(db, ctx, receta, producto.precio)


# --- Recetas de adiciones -------------------------------------------------------------------


def _modificador(db: Session, ctx: Contexto, modificador_id: uuid.UUID) -> Modificador:
    m = db.get(Modificador, modificador_id)
    if m is None or m.sede_id != ctx.sede_id:
        raise NoEncontrado("la adición", modificador_id)
    return m


@router.get("/modificadores/{modificador_id}/receta", response_model=RecetaSalida)
def ver_receta_modificador(
    modificador_id: uuid.UUID,
    ctx: Contexto = Depends(lector_recetas),
    db: Session = Depends(obtener_db),
):
    _modificador(db, ctx, modificador_id)
    receta = service.receta_vigente(db, modificador_id=modificador_id)
    if receta is None:
        raise NoEncontrado("la receta de la adición", modificador_id)
    return service.receta_salida(db, receta)


@router.put("/modificadores/{modificador_id}/receta", response_model=RecetaSalida)
def guardar_receta_modificador(
    modificador_id: uuid.UUID,
    datos: RecetaEntrada,
    ctx: Contexto = Depends(editor_recetas),
    db: Session = Depends(obtener_db),
):
    _modificador(db, ctx, modificador_id)
    receta = service.guardar_receta(db, ctx, datos, modificador_id=modificador_id)
    db.commit()
    return service.receta_salida(db, receta)


@router.get("/modificadores/{modificador_id}/costo", response_model=CostoSalida)
def costo_modificador(
    modificador_id: uuid.UUID,
    ctx: Contexto = Depends(lector_recetas),
    db: Session = Depends(obtener_db),
):
    m = _modificador(db, ctx, modificador_id)
    receta = service.receta_vigente(db, modificador_id=modificador_id)
    if receta is None:
        raise ErrorNegocio("SIN_RECETA", "Esta adición no tiene receta.", status=404)
    return service.costo_teorico(db, ctx, receta, m.precio)
