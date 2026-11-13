"""Comprobante interno de venta en PDF (#33, RF-14). No es factura electrónica."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.deps import Contexto
from app.modules.configuracion import service as configuracion
from app.modules.ventas.schemas import VentaSalida
from app.shared.pdf import e, fecha_hora, logo_data_uri, pagina, pesos

SERVICIO = {"local": "En local", "llevar": "Para llevar", "domicilio": "Domicilio"}
LEYENDA = "Documento interno, no es factura electrónica."


def _cantidad(valor: Decimal) -> str:
    texto = format(valor.normalize(), "f")
    return texto.replace(".", ",")


def html(db: Session, ctx: Contexto, v: VentaSalida, formato: str) -> str:
    negocio = configuracion.valor(db, ctx.sede_id, "negocio")
    datos = " · ".join(
        e(x)
        for x in (negocio.nit and f"NIT {negocio.nit}", negocio.direccion, negocio.telefono)
        if x
    )
    filas = []
    for i in v.items:
        detalle = "".join(
            f'<br><span class="suave">+ {e(m.nombre)}</span>' for m in i.modificadores
        )
        if i.nota:
            detalle += f'<br><span class="suave">{e(i.nota)}</span>'
        if i.descuento:
            detalle += f'<br><span class="suave">Descuento {pesos(-i.descuento)}</span>'
        filas.append(
            f"<tr><td>{_cantidad(i.cantidad)} × {e(i.producto)}{detalle}</td>"
            f'<td class="n">{pesos(i.subtotal)}</td></tr>'
        )
    totales = [("Subtotal", pesos(v.subtotal), "")]
    if v.descuento_total:
        motivo = f" · {e(v.descuento_motivo)}" if v.descuento_motivo else ""
        totales.append((f"Descuento{motivo}", pesos(-v.descuento_total), "peligro"))
    totales.append(("Total de la venta", pesos(v.total), "fuerte"))
    if v.propina:
        totales.append(("Propina (aparte, no es venta)", pesos(v.propina), "suave"))
    if v.valor_domicilio:
        totales.append(("Domicilio (del domiciliario)", pesos(v.valor_domicilio), "suave"))
    totales.append(("Total cobrado", pesos(v.cobrado), "fuerte grande"))
    pagos = "".join(
        f"<tr><td>{e(p.metodo)}"
        + (f' <span class="suave">· recibido {pesos(p.recibido)}</span>' if p.recibido else "")
        + f'</td><td class="n">{pesos(p.monto)}</td></tr>'
        for p in v.pagos
    )
    if v.cambio:
        pagos += (
            f'<tr><td class="fuerte">Cambio</td><td class="n fuerte">{pesos(v.cambio)}</td></tr>'
        )
    if not v.pagos:
        pagos = '<tr><td class="suave">Cortesía: sin cobro.</td><td></td></tr>'
    anulada = ""
    if v.estado == "anulada":
        anulada = f'<p class="peligro fuerte centro">ANULADA · {e(v.motivo_anulacion)}</p>'
    tabla_totales = "".join(
        f'<tr><td class="{c}">{t}</td><td class="n {c}">{m}</td></tr>' for t, m, c in totales
    )
    cuerpo = f"""
<div class="centro">
  <img class="logo" src="{logo_data_uri()}" alt="">
  <h1>{e(negocio.nombre)}</h1>
  <div class="suave">{datos}</div>
</div>
<div class="linea"></div>
<table>
  <tr><td class="fuerte grande">Comprobante n.º {v.numero:04d}</td>
      <td class="n suave">{fecha_hora(v.fecha)}</td></tr>
  <tr><td class="suave">{SERVICIO.get(v.tipo_servicio, "")}</td>
      <td class="n suave">Atendió: {e(v.cajero)}</td></tr>
</table>
{anulada}
<div class="linea"></div>
<table>{"".join(filas)}</table>
<div class="linea"></div>
<table>{tabla_totales}</table>
<div class="linea"></div>
<table><tr><td class="fuerte">Cómo pagó</td><td></td></tr>{pagos}</table>
<p class="leyenda">{LEYENDA}<br>¡Gracias por tu compra!</p>
"""
    lineas = len(v.items) + sum(len(i.modificadores) + bool(i.nota) for i in v.items)
    return pagina(
        formato,
        cuerpo,
        alto_estimado_mm=110 + 7 * (lineas + len(v.pagos)),
        anulado=v.estado == "anulada",
    )
