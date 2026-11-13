# Caso de control · Fase 1: una semana de compras y producción

Calculado a mano. `tests/test_control_fase1.py` lo ejecuta por la API y debe coincidir al peso.
Si una regla cambia, se recalcula aquí primero y luego se ajusta la prueba.

**Reglas que intervienen**
- RN-05 · PEPS: sale primero el lote que entró primero.
- Costo unitario de un lote = costo de la línea ÷ cantidad en unidad base, a 6 decimales.
- Costo de cada línea de movimiento = cantidad × costo unitario, redondeado a peso una sola vez (ROUND_HALF_UP).
- RN-10 · Un ajuste positivo entra al costo del último lote del ítem.

## Insumos y presentaciones

| Insumo | Unidad base | Presentación | Factor |
|---|---|---|---|
| Harina de trigo | g | Bolsa 1 kg | 1000 |
| Mantequilla | g | Barra 500 g | 500 |
| Huevos | und | Panal 30 | 30 |

## Receta: Pastel de pollo (rinde 12)

| Insumo | Cantidad |
|---|---|
| Harina | 600 g |
| Mantequilla | 250 g |
| Huevos | 4 und |

## Movimientos en orden

### Día 1 · Compra 1

| Insumo | Compra | Costo línea | Base | Costo unitario |
|---|---|---|---|---|
| Harina | 1 bolsa | $3.000 | 1000 g | $3 |
| Mantequilla | 1 barra | $9.000 | 500 g | $18 |
| Huevos | 1 panal | $13.500 | 30 und | $450 |

### Día 3 · Compra 2

| Insumo | Compra | Costo línea | Base | Costo unitario |
|---|---|---|---|---|
| Harina | 1 bolsa | $3.400 | 1000 g | $3,4 |
| Mantequilla | 1 barra | $9.500 | 500 g | $19 |
| Huevos | 1 panal | $14.100 | 30 und | $470 |

### Día 5 · Compra 3

| Insumo | Compra | Costo línea | Base | Costo unitario |
|---|---|---|---|---|
| Harina | 2 bolsas | $7.000 | 2000 g | $3,5 |
| Mantequilla | 1 barra | $10.000 | 500 g | $20 |
| Huevos | 1 panal | $15.000 | 30 und | $500 |

Total comprado: $25.500 + $27.000 + $32.000 = **$84.500**.

### Día 5 · Producción 1: 12 pasteles (la receta tal cual)

| Insumo | Cantidad | Lotes (PEPS) | Costo |
|---|---|---|---|
| Harina | 600 g | 600 × $3 (C1) | $1.800 |
| Mantequilla | 250 g | 250 × $18 (C1) | $4.500 |
| Huevos | 4 und | 4 × $450 (C1) | $1.800 |
| **Total** | | | **$8.100** |

Costo unitario: $8.100 ÷ 12 = **$675**. Lote P1: 12 und a $675.

### Día 6 · Merma: 200 g de mantequilla dañada

200 × $18 (C1) = **$3.600**. A la mantequilla de C1 le quedan 50 g.

### Día 6 · Producción 2: 18 pasteles (1,5 veces la receta)

| Insumo | Cantidad | Lotes (PEPS) | Costo |
|---|---|---|---|
| Harina | 900 g | 400 × $3 (C1) + 500 × $3,4 (C2) | $1.200 + $1.700 = $2.900 |
| Mantequilla | 375 g | 50 × $18 (C1) + 325 × $19 (C2) | $900 + $6.175 = $7.075 |
| Huevos | 6 und | 6 × $450 (C1) | $2.700 |
| **Total** | | | **$12.675** |

Costo unitario: $12.675 ÷ 18 = 704,1666… → **$704,166667**.
Lote P2: 18 und a $704,166667; su valor es 18 × 704,166667 = 12.675,000006 → **$12.675**.

### Día 7 · Ajuste por conteo: harina

Sistema: 500 g (C2) + 2000 g (C3) = 2500 g. Contado: 2550 g. Sobran 50 g, que entran al
costo del último lote (C3, $3,5): 50 × $3,5 = **$175**.

## Resultado

### Lotes con existencia

| Ítem | Lote | Quedan | Costo unitario | Valor |
|---|---|---|---|---|
| Harina | C2 | 500 g | $3,4 | $1.700 |
| Harina | C3 | 2000 g | $3,5 | $7.000 |
| Harina | Ajuste | 50 g | $3,5 | $175 |
| Mantequilla | C2 | 175 g | $19 | $3.325 |
| Mantequilla | C3 | 500 g | $20 | $10.000 |
| Huevos | C1 | 20 und | $450 | $9.000 |
| Huevos | C2 | 30 und | $470 | $14.100 |
| Huevos | C3 | 30 und | $500 | $15.000 |
| Pastel de pollo | P1 | 12 und | $675 | $8.100 |
| Pastel de pollo | P2 | 18 und | $704,166667 | $12.675 |

Los lotes C1 de harina y mantequilla quedan agotados y no aparecen.

### Stock por ítem

| Ítem | Hay | Valor |
|---|---|---|
| Harina | 2550 g | $8.875 |
| Mantequilla | 675 g | $13.325 |
| Huevos | 80 und | $38.100 |
| Pastel de pollo | 30 und | $20.775 |
| **Valor del inventario** | | **$81.075** |

Cuadre: $84.500 comprado − $3.600 de merma + $175 de ajuste = **$81.075**. La producción solo
pasa valor de los insumos al producto ($8.100 + $12.675), no lo crea ni lo destruye.

### Kardex de la mantequilla

| # | Tipo | Lote | Cantidad | Costo | Saldo | Saldo $ |
|---|---|---|---|---|---|---|
| 1 | compra | C1 | +500 | +$9.000 | 500 | $9.000 |
| 2 | compra | C2 | +500 | +$9.500 | 1000 | $18.500 |
| 3 | compra | C3 | +500 | +$10.000 | 1500 | $28.500 |
| 4 | consumo_produccion | C1 | −250 | −$4.500 | 1250 | $24.000 |
| 5 | merma | C1 | −200 | −$3.600 | 1050 | $20.400 |
| 6 | consumo_produccion | C1 | −50 | −$900 | 1000 | $19.500 |
| 7 | consumo_produccion | C2 | −325 | −$6.175 | 675 | $13.325 |

El saldo final coincide con el valor de la mantequilla en el stock.

## Pendiente

Aceptación con el negocio usando 3 recetas reales: la hacen los dueños con sus datos al cerrar la
fase. Este caso valida las reglas; no reemplaza esa prueba.
