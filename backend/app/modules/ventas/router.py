import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.db import obtener_db
from app.core.deps import Contexto, requiere, requiere_alguno
from app.core.idempotencia import Idempotencia, idempotencia
from app.modules.configuracion import service as configuracion
from app.modules.ventas import comprobante, service
from app.modules.ventas.descuentos import AutorizacionInvalida, contar_intento_fallido
from app.modules.ventas.schemas import AnulacionEntrada, VentaCrear, VentaSalida
from app.shared.paginacion import Pagina, ParamsPagina, RangoFechas
from app.shared.pdf import html_a_pdf

router = APIRouter(tags=["Ventas"])

lector_ventas = requiere_alguno("ventas.crear", "ventas.anular", "reportes.ver")


@router.post("/ventas", response_model=VentaSalida, status_code=201)
def crear_venta(
    datos: VentaCrear,
    ctx: Contexto = Depends(requiere("ventas.crear")),
    idem: Idempotencia = Depends(idempotencia(requerida=True)),
    db: Session = Depends(obtener_db),
):
    """Registra la venta completa en una transacción. Idempotency-Key obligatorio: un
    reintento del POS por una falla de red devuelve la misma venta sin duplicarla."""
    if (previa := idem.iniciar(db, ctx)) is not None:
        return previa
    try:
        venta = service.crear(db, ctx, datos)
    except AutorizacionInvalida as exc:
        # La venta se revierte, pero el intento fallido del autorizador sí queda (bloqueo).
        db.rollback()
        if exc.usuario_id:
            contar_intento_fallido(db, exc.usuario_id)
            db.commit()
        raise
    salida = service.salida(db, venta).model_dump(mode="json")
    idem.guardar(db, 201, salida)
    db.commit()
    return salida


@router.get("/ventas", response_model=Pagina[VentaSalida])
def listar_ventas(
    params: ParamsPagina = Depends(),
    rango: RangoFechas = Depends(),
    caja_sesion_id: uuid.UUID | None = Query(None),
    estado: Literal["pagada", "anulada"] | None = Query(None),
    ctx: Contexto = Depends(lector_ventas),
    db: Session = Depends(obtener_db),
):
    items, total = service.listar(db, ctx, params, rango, caja_sesion_id, estado)
    return Pagina(items=items, total=total, page=params.page, size=params.size)


@router.get("/ventas/{venta_id}", response_model=VentaSalida)
def ver_venta(
    venta_id: uuid.UUID, ctx: Contexto = Depends(lector_ventas), db: Session = Depends(obtener_db)
):
    return service.salida(db, service.obtener(db, ctx, venta_id))


@router.post("/ventas/{venta_id}/anular", response_model=VentaSalida)
def anular_venta(
    venta_id: uuid.UUID,
    datos: AnulacionEntrada,
    ctx: Contexto = Depends(requiere("ventas.anular")),
    idem: Idempotencia = Depends(idempotencia()),
    db: Session = Depends(obtener_db),
):
    """Anula con motivo: devuelve inventario a sus lotes y el dinero desde la caja abierta."""
    if (previa := idem.iniciar(db, ctx)) is not None:
        return previa
    venta = service.anular(db, ctx, venta_id, datos.motivo)
    salida = service.salida(db, venta).model_dump(mode="json")
    idem.guardar(db, 200, salida)
    db.commit()
    return salida


Formato = Literal["carta", "media_carta", "80mm", "58mm"]


@router.get("/ventas/{venta_id}/comprobante", response_class=Response)
def comprobante_pdf(
    venta_id: uuid.UUID,
    formato: Formato | None = Query(None, description="Por defecto, el de la configuración"),
    ctx: Contexto = Depends(lector_ventas),
    db: Session = Depends(obtener_db),
):
    """Comprobante interno en PDF (no es factura electrónica)."""
    venta = service.salida(db, service.obtener(db, ctx, venta_id))
    formato = formato or configuracion.valor(db, ctx.sede_id, "formato_comprobante")
    pdf = html_a_pdf(comprobante.html(db, ctx, venta, formato))
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="comprobante-{venta.numero:04d}.pdf"'},
    )
