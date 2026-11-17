"""Reportes de utilidad e inventario en tablas."""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.modules.reportes import cifras, inventario
from app.modules.reportes.esquemas import Reporte, col, seccion
from app.modules.reportes.periodo import Periodo
from app.modules.reportes.tablas import FILA_DESCUENTO, nuevo

CENTESIMA = Decimal("0.01")


def porcentaje(parte: int, total: int) -> Decimal:
    """parte/total en %, con dos decimales; 0 si el total es 0."""
    if not total:
        return Decimal("0.00")
    return (Decimal(parte) * 100 / Decimal(total)).quantize(CENTESIMA, ROUND_HALF_UP)


def reporte_utilidad_productos(db: Session, p: Periodo) -> Reporte:
    """Ventas − costo real PEPS por producto (sin cortesías, que son gasto aparte). Las líneas
    van antes del descuento sobre el total de la venta, que se resta en su propia fila."""
    filas = [
        {
            "producto": f.etiqueta,
            "unidades": f.unidades,
            "ventas": f.ventas,
            "costo": f.costo,
            "utilidad": f.ventas - f.costo,
            "margen": porcentaje(f.ventas - f.costo, f.ventas),
        }
        for f in cifras.ventas_por(db, p, "producto")
    ]
    descuento = cifras.descuento_global(db, p)
    if descuento:
        filas.append(
            {
                "producto": FILA_DESCUENTO,
                "unidades": None,
                "ventas": -descuento,
                "costo": 0,
                "utilidad": -descuento,
                "margen": None,
            }
        )
    return nuevo(
        db,
        p,
        "utilidad-productos",
        "Utilidad por producto",
        [
            seccion(
                "Por producto",
                [
                    col("producto", "Producto"),
                    col("unidades", "Unidades", "cantidad"),
                    col("ventas", "Ventas", "pesos"),
                    col("costo", "Costo real", "pesos"),
                    col("utilidad", "Utilidad", "pesos"),
                    col("margen", "Margen", "porcentaje"),
                ],
                filas,
                sumar=("ventas", "costo", "utilidad"),
            )
        ],
    )


def reporte_inventario_valorizado(db: Session, p: Periodo) -> Reporte:
    filas = [
        f.model_dump() | {"tipo_item": inventario.TIPOS_ITEM[f.tipo_item]}
        for f in inventario.inventario_valorizado(db, p.sede_id, p.hasta)
    ]
    return nuevo(
        db,
        p,
        "inventario-valorizado",
        "Inventario valorizado",
        [
            seccion(
                "Por lote",
                [
                    col("tipo_item", "Tipo"),
                    col("item", "Ítem"),
                    col("fecha_ingreso", "Ingresó", "fecha"),
                    col("cantidad", "Cantidad", "cantidad"),
                    col("costo_unitario", "Costo unitario", "cantidad"),
                    col("valor", "Valor", "pesos"),
                ],
                filas,
                sumar=("valor",),
            )
        ],
    )


def reporte_mermas(db: Session, p: Periodo) -> Reporte:
    filas = inventario.mermas_por(db, p)
    por_motivo: dict[str, int] = {}
    for f in filas:
        por_motivo[f.motivo] = por_motivo.get(f.motivo, 0) + f.costo
    return nuevo(
        db,
        p,
        "mermas",
        "Mermas",
        [
            seccion(
                "Por motivo",
                [col("motivo", "Motivo"), col("costo", "Costo", "pesos")],
                [{"motivo": m, "costo": c} for m, c in por_motivo.items()],
                sumar=("costo",),
            ),
            seccion(
                "Por ítem",
                [
                    col("item", "Ítem"),
                    col("motivo", "Motivo"),
                    col("cantidad", "Cantidad", "cantidad"),
                    col("costo", "Costo", "pesos"),
                ],
                [f.model_dump() for f in filas],
                sumar=("costo",),
            ),
        ],
    )


REPORTES_INVENTARIO = {
    "utilidad-productos": reporte_utilidad_productos,
    "inventario-valorizado": reporte_inventario_valorizado,
    "mermas": reporte_mermas,
}
