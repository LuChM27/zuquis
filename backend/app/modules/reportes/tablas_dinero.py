"""Reportes de dinero en tablas, armados con ``reportes.dinero``."""

from collections import defaultdict

from sqlalchemy.orm import Session

from app.modules.reportes import dinero
from app.modules.reportes.esquemas import Reporte, col, seccion
from app.modules.reportes.periodo import Periodo
from app.modules.reportes.tablas import nuevo

TIPOS_FLUJO = {
    "venta": "Ventas",
    "propina": "Propinas",
    "domicilio": "Domicilios",
    "pago_domiciliario": "Pago a domiciliarios",
    "abono": "Abonos de encargos",
    "saldo_encargo": "Saldos de encargos",
    "devolucion_abono": "Devolución de abonos",
    "gasto": "Gastos",
    "pago_compra": "Pagos a proveedores",
    "entrada_manual": "Entradas manuales",
    "salida_manual": "Salidas manuales",
    "reverso_anulacion": "Reversos por anulación",
}
FUENTES = {"caja": "Caja del día", "banco": "Cuenta bancaria", "duenos": "Dueños"}


def _agrupar(filas, clave, *campos) -> list[dict]:
    """Suma ``campos`` por ``clave`` sobre filas ya agregadas en SQL (pocas filas)."""
    acumulado: dict[str, dict] = defaultdict(lambda: dict.fromkeys(campos, 0))
    for f in filas:
        destino = acumulado[clave(f)]
        for c in campos:
            destino[c] += getattr(f, c)
    return [{"nombre": k} | v for k, v in acumulado.items()]


def reporte_gastos(db: Session, p: Periodo) -> Reporte:
    filas = dinero.gastos_por(db, p)
    por_categoria: dict[tuple, dict] = {}
    for f in filas:
        fila = por_categoria.setdefault(
            (f.categoria, f.cuenta_puc),
            {"categoria": f.categoria, "cuenta_puc": f.cuenta_puc, "n": 0, "monto": 0},
        )
        fila["n"] += f.n
        fila["monto"] += f.monto
    categorias = sorted(por_categoria.values(), key=lambda x: -x["monto"])
    fuentes = _agrupar(filas, lambda f: FUENTES.get(f.fuente, f.fuente), "n", "monto")
    meses = _agrupar(filas, lambda f: f.mes, "n", "monto")
    return nuevo(
        db,
        p,
        "gastos",
        "Gastos",
        [
            seccion(
                "Por categoría",
                [
                    col("categoria", "Categoría"),
                    col("cuenta_puc", "Cuenta PUC"),
                    col("n", "Gastos", "entero"),
                    col("monto", "Monto", "pesos"),
                ],
                categorias,
                sumar=("n", "monto"),
            ),
            seccion(
                "Por fuente",
                [
                    col("nombre", "Fuente"),
                    col("n", "Gastos", "entero"),
                    col("monto", "Monto", "pesos"),
                ],
                fuentes,
                sumar=("n", "monto"),
            ),
            seccion(
                "Por mes",
                [
                    col("nombre", "Mes"),
                    col("n", "Gastos", "entero"),
                    col("monto", "Monto", "pesos"),
                ],
                meses,
                sumar=("n", "monto"),
            ),
        ],
    )


def _cols_flujo(nombre: str) -> list:
    return [
        col("nombre", nombre),
        col("entra", "Entra", "pesos"),
        col("sale", "Sale", "pesos"),
        col("neto", "Neto", "pesos"),
    ]


def _con_neto(filas: list[dict]) -> list[dict]:
    return [f | {"neto": f["entra"] - f["sale"]} for f in filas]


def reporte_flujo_caja(db: Session, p: Periodo) -> Reporte:
    filas = dinero.flujo(db, p)
    sumar = ("entra", "sale", "neto")
    por_dia = _con_neto(_agrupar(filas, lambda f: f.dia, "entra", "sale"))
    por_tipo = _con_neto(
        _agrupar(filas, lambda f: TIPOS_FLUJO.get(f.tipo, f.tipo), "entra", "sale")
    )
    titulares = _agrupar(filas, lambda f: f.titular, "entra", "sale")
    por_titular = [{"titular": t.pop("nombre")} | t for t in _con_neto(titulares)]
    fuera = _con_neto(
        _agrupar(
            [f for f in filas if not f.en_caja],
            lambda f: f"{TIPOS_FLUJO.get(f.tipo, f.tipo)} · {f.metodo}",
            "entra",
            "sale",
        )
    )
    cols_titular = [
        col("titular", "Titular"),
        col("entra", "Entra", "pesos"),
        col("sale", "Sale", "pesos"),
        col("neto", "Neto", "pesos"),
    ]
    return nuevo(
        db,
        p,
        "flujo-caja",
        "Flujo de caja",
        [
            seccion(
                "Por día", [col("nombre", "Día", "fecha"), *_cols_flujo("")[1:]], por_dia, sumar
            ),
            seccion("Por tipo", _cols_flujo("Tipo"), por_tipo, sumar),
            seccion("Por titular", cols_titular, por_titular, sumar),
            seccion("Fuera de caja", _cols_flujo("Concepto"), fuera, sumar),
        ],
    )


def reporte_cierres(db: Session, p: Periodo) -> Reporte:
    filas = [f.model_dump() for f in dinero.cierres(db, p)]
    return nuevo(
        db,
        p,
        "cierres",
        "Cierres de caja",
        [
            seccion(
                "Arqueos",
                [
                    col("cerrada_en", "Cerrada", "fecha"),
                    col("cerrada_por", "Cerró"),
                    col("metodo", "Método"),
                    col("esperado", "Debería haber", "pesos"),
                    col("contado", "Contado", "pesos"),
                    col("diferencia", "Diferencia", "pesos"),
                ],
                filas,
                sumar=("esperado", "contado", "diferencia"),
            )
        ],
    )


def reporte_descuentos_cortesias(db: Session, p: Periodo) -> Reporte:
    filas = [
        f | {"cortesia": "Sí" if f["cortesia"] else "No"}
        for f in dinero.descuentos_cortesias(db, p)
    ]
    return nuevo(
        db,
        p,
        "descuentos-cortesias",
        "Descuentos y cortesías",
        [
            seccion(
                "Detalle",
                [
                    col("venta", "Venta", "entero"),
                    col("fecha", "Fecha", "fecha"),
                    col("cajero", "Cajero"),
                    col("motivo", "Motivo"),
                    col("autorizo", "Autorizó"),
                    col("cortesia", "Cortesía"),
                    col("descuento", "Descuento", "pesos"),
                    col("costo_cortesia", "Costo de la cortesía", "pesos"),
                ],
                filas,
                sumar=("descuento", "costo_cortesia"),
            )
        ],
    )


def reporte_domicilios(db: Session, p: Periodo) -> Reporte:
    return nuevo(
        db,
        p,
        "domicilios",
        "Domicilios",
        [
            seccion(
                "Por domiciliario",
                [
                    col("domiciliario", "Domiciliario"),
                    col("n", "Domicilios", "entero"),
                    col("valor", "Valor (de terceros)", "pesos"),
                ],
                dinero.domicilios_por(db, p),
                sumar=("n", "valor"),
            )
        ],
    )


def reporte_propinas(db: Session, p: Periodo) -> Reporte:
    return nuevo(
        db,
        p,
        "propinas",
        "Propinas",
        [
            seccion(
                "Por día",
                [col("dia", "Día", "fecha"), col("propinas", "Propinas (de terceros)", "pesos")],
                dinero.propinas_por_dia(db, p),
                sumar=("propinas",),
            )
        ],
    )


def reporte_ingresos_cancelacion(db: Session, p: Periodo) -> Reporte:
    return nuevo(
        db,
        p,
        "ingresos-cancelacion",
        "Ingresos por cancelación",
        [
            seccion(
                "Encargos cancelados",
                [
                    col("encargo", "Encargo", "entero"),
                    col("cliente", "Cliente"),
                    col("fecha", "Cancelado", "fecha"),
                    col("motivo", "Motivo"),
                    col("devuelto", "Devuelto", "pesos"),
                    col("retenido", "Retenido (ingreso)", "pesos"),
                ],
                dinero.cancelaciones(db, p),
                sumar=("devuelto", "retenido"),
            )
        ],
    )


REPORTES_DINERO = {
    "gastos": reporte_gastos,
    "flujo-caja": reporte_flujo_caja,
    "cierres": reporte_cierres,
    "descuentos-cortesias": reporte_descuentos_cortesias,
    "domicilios": reporte_domicilios,
    "propinas": reporte_propinas,
    "ingresos-cancelacion": reporte_ingresos_cancelacion,
}
