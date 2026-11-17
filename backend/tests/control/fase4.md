# Caso de control de la Fase 4: una semana de reportes

Semana del lunes 9 al domingo 15 de noviembre de 2026, generada por `app/demo/semana.py`. Todo lo
calculado aquí es a mano; la prueba `tests/test_control_fase4.py` compara los reportes contra estas
cifras al peso.

## Carta e insumos

| Ítem | Dato |
|---|---|
| Harina de trigo (g) | Lote 1: lunes, 3.000 g por $9.000 (3 $/g), de contado fuera de caja. Lote 2: miércoles, 10.000 g por $40.000 (4 $/g), por pagar con fecha límite viernes 13 |
| Leche entera (ml) | Lunes, 20.000 ml por $60.000 (3 $/ml), por pagar sin fecha |
| Pan de bono (vitrina) | $2.000. Receta: 100 g de harina por pan |
| Café con leche (preparado) | $5.000. Receta: 200 ml de leche → costo $600 |

Producción de pan (PEPS sobre la harina):
- Lunes: 20 panes con 2.000 g del lote 1 = $6.000 → **$300 por pan**.
- Jueves: 20 panes con 1.000 g del lote 1 ($3.000) + 1.000 g del lote 2 ($4.000) = $7.000 → **$350 por pan**.

## Hechos de la semana

| Día | Hecho | Total venta | Costo PEPS |
|---|---|---|---|
| Lun 11:00 | V1: 3 panes, efectivo | 6.000 | 3 × 300 = 900 |
| Lun 16:00 | V2: 2 cafés + propina 1.000, Nequi 11.000 | 10.000 | 1.200 |
| Mar 09:00 | Gasto arriendo $500.000 del banco (Bancolombia) | | |
| Mar 12:00 | V3: 5 panes, descuento $1.000 sobre el total, efectivo | 9.000 | 1.500 |
| Mar 17:00 | V4: 1 café de cortesía (100 %) | 0 | 600 (gasto de cortesía) |
| Mar 18:00 | V5: 2 panes, efectivo 4.000, **anulada** | — | (vuelve al lote) |
| Mié 09:00 | Compra harina lote 2 por pagar | | |
| Mié 11:00 | E1 (Ana): torta $50.000 para el viernes; abono 20.000 efectivo | | |
| Mié 13:00 | V6: 4 panes a domicilio + domicilio 3.000 (Carlos), efectivo 11.000 | 8.000 | 1.200 |
| Mié 19:00 | Liquidación de Carlos: 3.000 | | |
| Jue 09:00 | E2 (Beto): postre $30.000; abono 10.000 Nequi | | |
| Jue 10:00 | Producción de 20 panes | | |
| Jue 12:00 | Gasto aseo $12.000 de la caja | | |
| Jue 15:00 | V7: 6 panes, efectivo (quedan 2 del lote del lunes) | 12.000 | 6 × 300 = 1.800 |
| Jue 18:00 | E2 cancelado: devuelve 4.000, retiene 6.000 | | |
| Jue 20:00 | Cierre con $2.000 de menos en efectivo | | |
| Vie 10:00 | Gasto papelería $8.000 de caja, **anulado** | | |
| Vie 11:00 | V8: 4 panes, Bancolombia | 8.000 | 2 × 300 + 2 × 350 = 1.300 |
| Vie 15:00 | E1 entregado: saldo 30.000 efectivo (crea la venta) | 50.000 | 0 (ítem sin receta) |
| Sáb 10:00 | V9: 3 cafés, efectivo | 15.000 | 1.800 |
| Sáb 19:00 | Mermas: 2 panes vencidos (2 × 350 = 700) y 500 g de harina dañada (500 × 4 = 2.000) | | |

## Totales de la semana

| Cifra | Cálculo | Valor |
|---|---|---|
| Ventas | 6.000 + 10.000 + 9.000 + 0 + 8.000 + 12.000 + 8.000 + 15.000 + 50.000 | **118.000** |
| Número de ventas (pagadas) | V1, V2, V3, V4, V6, V7, V8, V9, E1 | 9 |
| Cortesías | V4 | 1 |
| Costo de insumos (sin cortesía) | 900 + 1.200 + 1.500 + 1.200 + 1.800 + 1.300 + 1.800 + 0 | **9.700** |
| Costo de cortesías | V4 | 600 |
| Descuentos | 1.000 + 5.000 (cortesía) | 6.000 |
| Propinas | V2 | 1.000 |
| Domicilios | V6 | 3.000 |
| Gastos | 500.000 + 12.000 (papelería anulada) | **512.000** |
| Mermas | 700 + 2.000 | 2.700 |
| Ingresos por cancelación | E2 | 6.000 |
| Anuladas | V5 | 1 |
| Utilidad (cascada) | 118.000 − 9.700 − 600 − 512.000 − 2.700 + 6.000 | **−401.000** |
| Costo de insumos % (semana 46) | 9.700 / 118.000 | 8,22 % |

## Utilidad por producto (sin cortesías; líneas antes del descuento sobre el total)

| Producto | Unidades | Ventas | Costo | Utilidad |
|---|---|---|---|---|
| Pan de bono | 3 + 5 + 4 + 6 + 4 = 22 | 6.000 + 10.000 + 8.000 + 12.000 + 8.000 = 44.000 | 6.700 | 37.300 |
| Café con leche | 2 + 3 = 5 | 25.000 | 3.000 | 22.000 |
| Torta de chocolate 2 lb | 1 | 50.000 | 0 | 50.000 |
| Descuento sobre el total | | −1.000 | | −1.000 |
| **Total** | | **118.000** | **9.700** | **108.300** |

## Inventario valorizado al domingo 15

| Lote | Cantidad | Costo unitario | Valor |
|---|---|---|---|
| Harina lote 2 | 10.000 − 1.000 − 500 = 8.500 g | 4 | 34.000 |
| Leche | 20.000 − 200 × (2 + 1 + 3) = 18.800 ml | 3 | 56.400 |
| Pan lote jueves | 20 − 2 (V8) − 2 (merma) = 16 | 350 | 5.600 |
| **Total** | | | **96.000** |

## Otros

- Producido contra vendido (pan): producido 40, vendido 22.
- Cuentas por pagar al domingo: harina lote 2 vencida (límite viernes) 40.000; leche sin fecha, 6 días → 0–15 días 60.000.
- Encargos: 1 entregado y 1 cancelado en la semana 46; abonos de encargos sin entregar al domingo: 0.
- Clientes que más encargan: Ana Gómez, 1 encargo, 50.000.
- Por cajero (un solo usuario): vendido 118.000, descuentos 1.000, 1 cortesía, diferencia de cierres −2.000.
- Dashboard del miércoles (después de cerrar): ventas 8.000, 1 venta, gastos 0, ganancia 8.000 − 1.200 = 6.800, ticket 8.000.

## Reporte PUC por cuenta

| Cuenta | Origen | Valor |
|---|---|---|
| 4120 | Valor bruto de las ventas sin cortesía: 6.000 + 10.000 + 10.000 + 8.000 + 12.000 + 8.000 + 15.000 + 50.000 | 119.000 |
| 4175 | Descuento V3 | 1.000 |
| 6120 | Costo de ventas | 9.700 |
| 5295 | Cortesía 600 + mermas 2.700 | 3.300 |
| 2380 | Propina 1.000 + domicilio 3.000 | 4.000 |
| 4295 | Retenido E2 | 6.000 |
| 2805 | Abonos 20.000 + 10.000 | 30.000 |
| 5120 | Arriendo | 500.000 |
| 5195 | Aseo (papelería anulada) | 12.000 |
| 1105 | Efectivo recibido: V1 6.000 + V3 9.000 + V6 11.000 + abono E1 20.000 + V7 12.000 + saldo E1 30.000 + V9 15.000 (la venta anulada V5 no cuenta) | 103.000 |
| 1110 | Nequi 11.000 + abono E2 10.000 + Bancolombia 8.000 | 29.000 |

## Flujo de caja

- Entra por la caja: 6.000 + 11.000 + 9.000 + 4.000 (V5) + 11.000 + 20.000 + 10.000 + 12.000 + 8.000 + 30.000 + 15.000 + 8.000 (reverso de la papelería anulada) = **144.000**.
- Sale por la caja: 4.000 (reverso de V5) + 3.000 (domiciliario) + 4.000 (devolución E2) + 12.000 (aseo) + 8.000 (papelería) = **31.000**.
- Fuera de caja: compra de harina de contado 9.000 + arriendo 500.000 = **509.000**.
