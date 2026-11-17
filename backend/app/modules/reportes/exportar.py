"""Exportación de un ``Reporte`` a Excel (openpyxl) y PDF (WeasyPrint) (RF-43).

Una sola rutina por formato sirve a todos los reportes porque comparten la misma forma. En el
Excel los montos son números (no texto) y los totales son fórmulas ``SUM`` que dan lo mismo que
el JSON del reporte.
"""

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from app.modules.reportes.esquemas import Columna, Reporte, Seccion
from app.shared import pdf
from app.shared.fechas import a_local

FORMATO_PESOS = '"$"#,##0'
FORMATOS = {"pesos": FORMATO_PESOS, "entero": "0", "cantidad": "#,##0.####", "porcentaje": "0.00"}
FORMULA = ("=", "+", "-", "@")
PROHIBIDOS = str.maketrans({c: " " for c in "[]:*?/\\"})


def _fecha(d: date) -> str:
    return f"{d:%d/%m/%Y}"


def encabezado(r: Reporte, negocio: str) -> list[str]:
    generado = pdf.fecha_hora(r.generado_en)
    return [
        f"{negocio} · {r.titulo}",
        f"Sede: {r.sede}",
        f"Del {_fecha(r.desde)} al {_fecha(r.hasta)}",
        f"Generado el {generado}",
    ]


def _tipo(c: Columna, fila: dict[str, Any]) -> str:
    return fila.get("_tipo", c.tipo) if c.clave == "valor" else c.tipo


def _celda_excel(valor: Any, tipo: str) -> Any:
    if valor is None:
        return None
    if tipo == "fecha":
        if isinstance(valor, str):
            return _fecha(date.fromisoformat(valor[:10]))
        return _fecha(a_local(valor).date() if isinstance(valor, datetime) else valor)
    if tipo in ("cantidad", "porcentaje"):
        return Decimal(valor)
    return valor


def a_xlsx(r: Reporte, negocio: str) -> bytes:
    libro = Workbook()
    libro.remove(libro.active)
    for s in r.secciones:
        _hoja(libro, r, s, negocio)
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _hoja(libro: Workbook, r: Reporte, s: Seccion, negocio: str) -> None:
    hoja = libro.create_sheet(s.titulo.translate(PROHIBIDOS)[:31])
    for i, linea in enumerate(encabezado(r, negocio), start=1):
        hoja.cell(row=i, column=1, value=linea).font = Font(bold=i == 1, size=13 if i == 1 else 10)
    fila_titulos = 6
    for j, c in enumerate(s.columnas, start=1):
        celda = hoja.cell(row=fila_titulos, column=j, value=c.titulo)
        celda.font = Font(bold=True)
        hoja.column_dimensions[get_column_letter(j)].width = max(14, len(c.titulo) + 4)
    primera = fila_titulos + 1
    for i, fila in enumerate(s.filas, start=primera):
        for j, c in enumerate(s.columnas, start=1):
            tipo = _tipo(c, fila)
            celda = hoja.cell(row=i, column=j, value=_celda_excel(fila.get(c.clave), tipo))
            if isinstance(celda.value, str) and celda.value[:1] in FORMULA:
                celda.data_type = "s"  # texto de usuario: nunca se evalúa como fórmula
            if tipo in FORMATOS:
                celda.number_format = FORMATOS[tipo]
                celda.alignment = Alignment(horizontal="right")
    if s.totales and s.filas:
        ultima = primera + len(s.filas) - 1
        fila_total = ultima + 1
        hoja.cell(row=fila_total, column=1, value="Total").font = Font(bold=True)
        for j, c in enumerate(s.columnas, start=1):
            if c.clave in s.totales:
                letra = get_column_letter(j)
                celda = hoja.cell(
                    row=fila_total, column=j, value=f"=SUM({letra}{primera}:{letra}{ultima})"
                )
                celda.font = Font(bold=True)
                celda.number_format = FORMATOS.get(c.tipo, "General")


def _celda_pdf(valor: Any, tipo: str) -> str:
    if valor is None:
        return ""
    if tipo == "pesos":
        return pdf.pesos(int(valor))
    if tipo == "porcentaje":
        return f"{Decimal(valor):.2f}".replace(".", ",") + " %"
    if tipo == "cantidad":
        return f"{Decimal(valor).normalize():f}".replace(".", ",")
    if tipo == "fecha":
        return pdf.e(_celda_excel(valor, "fecha"))
    if tipo == "entero":
        return f"{int(valor):,}".replace(",", ".")
    return pdf.e(valor)


def _alineacion(tipo: str) -> str:
    return "" if tipo in ("texto", "fecha") else "n"


def a_pdf(r: Reporte, negocio: str) -> bytes:
    lineas = encabezado(r, negocio)
    partes = [
        f'<div><img class="logo" src="{pdf.logo_data_uri()}" alt=""></div>',
        f"<h1>{pdf.e(lineas[0])}</h1>",
        *(f'<div class="suave">{pdf.e(x)}</div>' for x in lineas[1:]),
    ]
    for s in r.secciones:
        cabeza = "".join(
            f'<td class="{_alineacion(c.tipo)} fuerte">{pdf.e(c.titulo)}</td>' for c in s.columnas
        )
        cuerpo = "".join(
            "<tr>"
            + "".join(
                f'<td class="{_alineacion(_tipo(c, f))}">'
                f"{_celda_pdf(f.get(c.clave), _tipo(c, f))}</td>"
                for c in s.columnas
            )
            + "</tr>"
            for f in s.filas
        )
        pie = ""
        if s.totales and s.filas:
            pie = (
                '<tr class="fuerte">'
                + "".join(
                    f'<td class="n">{_celda_pdf(s.totales[c.clave], c.tipo)}</td>'
                    if c.clave in s.totales
                    else ("<td>Total</td>" if i == 0 else "<td></td>")
                    for i, c in enumerate(s.columnas)
                )
                + "</tr>"
            )
        vacio = '<tr><td class="suave">Sin datos en este rango</td></tr>' if not s.filas else ""
        partes.append(
            f'<div class="linea"></div><h2>{pdf.e(s.titulo)}</h2>'
            f"<table><tr>{cabeza}</tr>{cuerpo}{vacio}{pie}</table>"
        )
    return pdf.html_a_pdf(pdf.pagina("carta", "".join(partes)))
