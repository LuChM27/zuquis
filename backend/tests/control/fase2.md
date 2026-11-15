# Caso de control · Fase 2: un día completo de ventas

Calculado a mano. `tests/test_control_fase2.py` lo ejecuta por la API y debe coincidir al peso.
Si una regla cambia, se recalcula aquí primero y luego se ajusta la prueba.

**Reglas que intervienen**
- RN-05/RN-06/RN-08 · PEPS: cada venta descuenta del lote más antiguo, sea insumo (receta) o
  producto de vitrina.
- Costo de cada línea de movimiento = cantidad × costo unitario del lote, redondeado a peso.
- Las adiciones se cobran por unidad; una adición sin receta no descuenta inventario.
- Descuento por porcentaje redondeado a peso; por encima del tope del rol necesita autorización
  (RN-16). La cortesía (100 %) deja la venta en $0 y aun así descuenta inventario.
- El pago se reparte en orden: primero la venta, luego la propina. La propina va aparte en caja.
- RN-03 · Una anulación devuelve el inventario a los mismos lotes y el dinero sale de la caja
  abierta por el mismo método.
- Esperado en efectivo = base + ventas en efectivo + propinas en efectivo − gastos de caja.

## Inventario de partida (compras por pagar, no tocan la caja)

| Insumo | Compra | Costo | Costo unitario |
|---|---|---|---|
| Café molido | C1: 500 g | $20.000 | $40/g |
| Leche | C1: 2.000 ml | $6.000 | $3/ml |
| Leche | C2: 4.000 ml | $14.000 | $3,5/ml |
| Masa de pastel | C1: 600 g | $3.000 | $5/g |
| Masa de pastel | C2: 600 g | $3.600 | $6/g |

**Producción** del Pastel de pollo (receta: 600 g de masa, rinde 12):
- P1: 12 pasteles con la masa C1 → $3.000 → **$250** c/u.
- P2: 12 pasteles con la masa C2 → $3.600 → **$300** c/u.

## Carta

| Producto | Tipo | Precio | Receta | Costo |
|---|---|---|---|---|
| Café americano | preparado | $3.000 | 10 g café | $400 |
| Capuchino | preparado | $6.000 | 10 g café + 150 ml leche | $400 + leche |
| Malteada | preparado | $16.000 | 300 ml leche | leche |
| Pastel de pollo | vitrina | $4.500 | — | lote |
| + Bola de helado (adición) | — | $5.000 | sin receta | $0 |

Con leche C1 ($3): capuchino $850, malteada $900. Con leche C2 ($3,5): capuchino $925, malteada $1.050.

## El día

Apertura con base de **$100.000** en efectivo. El administrador vende todo menos la V10, que la
hace un cajero con tope de descuento del 10 %.

| # | Venta | Total | Propina | Pago | Costo |
|---|---|---|---|---|---|
| V1 | 2 cafés | $6.000 | | Efectivo $6.000 (recibe $10.000, cambio $4.000) | $800 |
| V2 | capuchino + pastel | $10.500 | | Nequi | $850 + $250 = $1.100 |
| V3 | malteada + bola de helado | $21.000 | $2.000 | Efectivo $23.000 | $900 |
| V4 | 3 pasteles | $13.500 | | Bre-B | $750 |
| V5 | 2 capuchinos | $12.000 | | Efectivo $7.000 + Nequi $5.000 | $1.700 |
| V6 | malteada | $16.000 | | Bancolombia | $900 |
| V7 | café | $3.000 | | Efectivo | $400 |
| V8 | 4 pasteles | $18.000 | | Efectivo $10.000 + Bre-B $8.000 | $1.000 |
| V9 | capuchino | $6.000 | $1.000 | Nequi $7.000 | $850 |
| V10 | 2 malteadas, 25 % "cliente frecuente" (autoriza el jefe con PIN) | $32.000 − $8.000 = $24.000 | | Efectivo | $1.800 |
| V11 | café + pastel | $7.500 | | Efectivo | $400 + $250 = $650 |
| V12 | pastel, cortesía 100 % | $0 | | — | $250 |
| V13 | 2 capuchinos | $12.000 | | Nequi | ver leche ↓ = $1.750 |
| V14 | 3 cafés | $9.000 | | Efectivo | $1.200 |
| V15 | malteada | $16.000 | | Nequi $10.000 + Efectivo $6.000 | $1.050 |
| V16 | 2 pasteles | $9.000 | | Bancolombia | $500 |
| V17 | capuchino + café | $9.000 | $1.000 | Efectivo $10.000 | $925 + $400 = $1.325 |
| V18 | 2 pasteles | $9.000 | | Bre-B | $600 (P2) → **anulada** |
| V19 | malteada | $16.000 | | Efectivo | $1.050 |
| V20 | café | $3.000 | | Nequi | $400 |

**Leche por PEPS** (C1 tiene 2.000 ml): V2 150 · V3 300 · V5 300 · V6 300 · V9 150 · V10 600 →
quedan 200 ml en C1. V13 necesita 300: 200 × $3 + 100 × $3,5 = $950 de leche + $800 de café =
**$1.750**. De ahí en adelante todo sale de C2: V15 300 · V17 150 · V19 300.

**Pasteles por PEPS** (P1 tiene 12): V2 1 · V4 3 · V8 4 · V11 1 · V12 1 · V16 2 = 12 → P1 se acaba.
V18 toma 2 de P2 ($600) y la anulación los devuelve a P2.

**Gastos pagados de la caja (efectivo):** papelería $8.000 y servicio de energía $25.000 = **$33.000**.

## Resultados

**Ventas del día** (sin la anulada): **$211.500** en 19 ventas. Descuentos: $8.000 (V10) +
$4.500 (cortesía) = $12.500. Propinas: **$4.000** (efectivo $3.000, Nequi $1.000).

**Costo de ventas** (sin la anulada): **$18.375**, de los cuales $250 son la cortesía.

**Caja por método**

| Método | Ventas | Propinas | Anulación | Gastos | Esperado |
|---|---|---|---|---|---|
| Efectivo | $118.500 | $3.000 | | −$33.000 | base $100.000 → **$188.500** |
| Nequi | $46.500 | $1.000 | | | **$47.500** |
| Bre-B | $30.500 | | −$9.000 | | **$21.500** |
| Bancolombia | $25.000 | | | | **$25.000** |

Resumen del turno: ventas registradas en caja $220.500 (incluye la V18), anulaciones $9.000,
propinas $4.000, gastos $33.000.

**Cierre:** se cuentan $188.000 en efectivo (**diferencia −$500**, con observación) y el resto
exacto.

**Stock final por lote**

| Ítem | Lote | Disponible | Costo unitario | Valor |
|---|---|---|---|---|
| Café molido | C1 | 340 g | $40 | $13.600 |
| Leche | C2 | 3.150 ml | $3,5 | $11.025 |
| Masa de pastel | — | 0 | | $0 |
| Pastel de pollo | P2 | 12 und | $300 | $3.600 |

Valor del inventario: **$28.225** = compras $46.600 − costo de ventas $18.375.
