"""Reportes en tablas (RF-42): cada uno es un ``Reporte`` armado con las funciones de ``cifras``."""

from collections.abc import Callable
from datetime import UTC

from sqlalchemy.orm import Session

from app.modules.configuracion.models import Sede
from app.modules.reportes import cifras
from app.modules.reportes.esquemas import Reporte, Seccion, col, seccion
from app.modules.reportes.periodo import Periodo
from app.shared.fechas import ahora

FILA_DESCUENTO = "Descuento sobre el total de la venta"


def nuevo(db: Session, p: Periodo, tipo: str, titulo: str, secciones: list[Seccion]) -> Reporte:
    sede = db.get(Sede, p.sede_id)
    return Reporte(
        tipo=tipo,
        titulo=titulo,
        sede=sede.nombre if sede else "",
        desde=p.desde,
        hasta=p.hasta,
        generado_en=ahora().astimezone(UTC),
        secciones=secciones,
    )


def _resumen_ventas(t: cifras.Totales) -> Seccion:
    filas = [
        ("Ventas (sin propinas ni domicilios)", t.ventas, "pesos"),
        ("Número de ventas", t.n_ventas, "entero"),
        ("Costo de insumos", t.costo_insumos, "pesos"),
        ("Descuentos y cortesías", t.descuentos, "pesos"),
        ("Cortesías", t.n_cortesias, "entero"),
        ("Costo de las cortesías", t.costo_cortesias, "pesos"),
        ("Propinas (de terceros)", t.propinas, "pesos"),
        ("Domicilios (de terceros)", t.domicilios, "pesos"),
        ("Ingresos por cancelación", t.ingresos_cancelacion, "pesos"),
        ("Ventas anuladas", t.anuladas, "entero"),
    ]
    return Seccion(
        titulo="Resumen",
        columnas=[col("concepto", "Concepto"), col("valor", "Valor", "pesos")],
        filas=[{"concepto": c, "valor": v, "_tipo": tipo} for c, v, tipo in filas],
    )


def _filas_venta(filas: list[cifras.FilaVentas], clave: str) -> list[dict]:
    return [{clave: f.etiqueta, "n": f.n, "ventas": f.ventas, "costo": f.costo} for f in filas]


def _por_linea(db: Session, p: Periodo, por: cifras.AgrupaVentas, titulo: str) -> Seccion:
    filas = [
        {"nombre": f.etiqueta, "unidades": f.unidades, "ventas": f.ventas, "costo": f.costo}
        for f in cifras.ventas_por(db, p, por)
    ]
    descuento = cifras.descuento_global(db, p)
    if descuento:
        filas.append({"nombre": FILA_DESCUENTO, "unidades": None, "ventas": -descuento, "costo": 0})
    return seccion(
        titulo,
        [
            col("nombre", "Producto" if por == "producto" else "Categoría"),
            col("unidades", "Unidades", "cantidad"),
            col("ventas", "Ventas", "pesos"),
            col("costo", "Costo de insumos", "pesos"),
        ],
        filas,
        sumar=("ventas", "costo"),
    )


def _por_venta(titulo: str, clave: str, nombre: str, filas: list[cifras.FilaVentas]) -> Seccion:
    return seccion(
        titulo,
        [
            col(clave, nombre),
            col("n", "Ventas", "entero"),
            col("ventas", "Valor", "pesos"),
            col("costo", "Costo de insumos", "pesos"),
        ],
        _filas_venta(filas, clave),
        sumar=("n", "ventas", "costo"),
    )


def reporte_ventas(db: Session, p: Periodo) -> Reporte:
    dias = [
        {"dia": f.clave, "n": f.n, "ventas": f.ventas, "costo": f.costo}
        for f in cifras.ventas_por(db, p, "dia")
    ]
    metodos = [
        {"metodo": f.etiqueta, "n": f.n, "ventas": f.ventas}
        for f in cifras.ventas_por(db, p, "metodo")
    ]
    return nuevo(
        db,
        p,
        "ventas",
        "Ventas",
        [
            _resumen_ventas(cifras.totales(db, p)),
            seccion(
                "Por día",
                [
                    col("dia", "Día", "fecha"),
                    col("n", "Ventas", "entero"),
                    col("ventas", "Valor", "pesos"),
                    col("costo", "Costo de insumos", "pesos"),
                ],
                dias,
                sumar=("n", "ventas", "costo"),
            ),
            _por_linea(db, p, "producto", "Por producto"),
            _por_linea(db, p, "categoria", "Por categoría"),
            seccion(
                "Por método de pago",
                [
                    col("metodo", "Método"),
                    col("n", "Ventas", "entero"),
                    col("ventas", "Cobrado (con propinas y domicilios)", "pesos"),
                ],
                metodos,
                sumar=("ventas",),
            ),
            _por_venta(
                "Por tipo de servicio", "servicio", "Servicio", cifras.ventas_por(db, p, "servicio")
            ),
            _por_venta("Por cajero", "cajero", "Cajero", cifras.ventas_por(db, p, "cajero")),
        ],
    )


REPORTES: dict[str, Callable[[Session, Periodo], Reporte]] = {
    "ventas": reporte_ventas,
}
