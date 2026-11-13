"""PDF a partir de HTML con WeasyPrint (comprobantes, resúmenes de cierre, reportes).

WeasyPrint necesita Pango del sistema: viene en la imagen Docker y en CI. En un equipo sin esas
librerías (Windows sin GTK) la API sigue funcionando y solo los PDF responden 503.
"""

import base64
import html
from datetime import datetime
from functools import cache
from pathlib import Path

from app.shared.errores import ErrorNegocio
from app.shared.fechas import a_local

RECURSOS = Path(__file__).resolve().parent.parent / "recursos"

# Tamaños de página: carta y media carta para impresora normal; 80 y 58 mm para térmica.
FORMATOS = {
    "carta": {"ancho": "216mm", "alto": "279mm", "margen": "16mm", "letra": "10.5pt"},
    "media_carta": {"ancho": "140mm", "alto": "216mm", "margen": "10mm", "letra": "9.5pt"},
    "80mm": {"ancho": "80mm", "alto": None, "margen": "4mm", "letra": "8.5pt"},
    "58mm": {"ancho": "58mm", "alto": None, "margen": "3mm", "letra": "7.5pt"},
}


@cache
def pdf_disponible() -> bool:
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


def html_a_pdf(documento: str) -> bytes:
    if not pdf_disponible():
        raise ErrorNegocio(
            "PDF_NO_DISPONIBLE",
            "Este equipo no puede generar PDF (faltan las librerías de WeasyPrint).",
            status=503,
        )
    from weasyprint import HTML

    return HTML(string=documento).write_pdf()


@cache
def logo_data_uri() -> str:
    datos = (RECURSOS / "logo.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(datos).decode()


def e(texto: object) -> str:
    """Escapa texto para HTML."""
    return html.escape("" if texto is None else str(texto))


def pesos(valor: int, signo: bool = False) -> str:
    """$684.500, −$3.000 (como el frontend)."""
    texto = f"${abs(valor):,}".replace(",", ".")
    if valor < 0:
        return "−" + texto
    return ("+" + texto) if signo and valor > 0 else texto


def fecha_hora(momento: datetime) -> str:
    """13/11/2026 2:42 p. m. en hora de Colombia."""
    local = a_local(momento)
    hora = local.hour % 12 or 12
    sufijo = "a. m." if local.hour < 12 else "p. m."
    return f"{local:%d/%m/%Y} {hora}:{local:%M} {sufijo}"


def pagina(formato: str, cuerpo: str, alto_estimado_mm: int = 200, anulado: bool = False) -> str:
    """Documento HTML completo con el estilo de la marca y el tamaño de papel pedido."""
    f = FORMATOS[formato]
    # Las térmicas no tienen alto fijo: se estima por el contenido para no cortar ni desperdiciar.
    alto = f["alto"] or f"{max(alto_estimado_mm, 80)}mm"
    marca_agua = '<div class="anulado">ANULADA</div>' if anulado else ""
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><style>
@page {{ size: {f["ancho"]} {alto}; margin: {f["margen"]}; }}
body {{ font-family: "Montserrat", "DejaVu Sans", sans-serif; font-size: {f["letra"]};
  color: #4a3428; margin: 0; }}
h1 {{ font-family: "Cormorant Garamond", "DejaVu Serif", serif; font-weight: 600;
  font-size: 1.9em; margin: 0.1em 0; }}
.centro {{ text-align: center; }}
.suave {{ color: #7a5e50; }}
.logo {{ width: 22mm; height: 22mm; border-radius: 50%; }}
table {{ width: 100%; border-collapse: collapse; }}
td {{ padding: 0.25em 0; vertical-align: top; }}
td.n {{ text-align: right; white-space: nowrap; padding-left: 0.6em; }}
.linea {{ border-top: 1px solid #ead9b4; margin: 0.5em 0; }}
.fuerte {{ font-weight: 700; }}
.grande {{ font-size: 1.25em; }}
.peligro {{ color: #8e1f18; }}
.leyenda {{ margin-top: 1em; font-size: 0.85em; color: #7a5e50; text-align: center; }}
.anulado {{ position: fixed; top: 38%; left: 0; right: 0; text-align: center;
  font-size: 4.2em; font-weight: 700; color: rgba(179, 38, 30, 0.22);
  transform: rotate(-28deg); letter-spacing: 0.08em; }}
</style></head><body>{marca_agua}{cuerpo}</body></html>"""
