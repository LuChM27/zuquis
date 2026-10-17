# Propuesta de códigos PUC: para validar con el contador

Punto de partida para RF-22 y RF-43. Usa cuentas de 4 dígitos del PUC para comerciantes (Decreto 2650 de 1993). **No es una decisión contable**: el contador debe confirmar o corregir cada código y, si quiere, bajar a subcuenta de 6 dígitos. El sistema guarda el código como texto editable por categoría, así que cambiarlo no exige tocar código.

Se necesita validado antes de la fase 4 (reportes y exportación).

## Ingresos

| Concepto en el sistema | Cuenta propuesta | Nota para el contador |
|---|---|---|
| Ventas de productos (POS y encargos entregados) | 4140 Hoteles y restaurantes | Alternativas: 4120 Industrias manufactureras (si se considera fabricación de alimentos) o 4135 Comercio. Depende de la actividad CIIU registrada en el RUT. |
| Descuentos en ventas | 4175 Devoluciones en ventas (DB) | Se reportan aparte del ingreso bruto. |
| Abono retenido por cancelación de encargo (RN-22) | 4295 Diversos | Depende de la aprobación de RN-22. |

## Costo de ventas

| Concepto | Cuenta propuesta | Nota |
|---|---|---|
| Costo real PEPS de lo vendido | 6140 Hoteles y restaurantes | Debe ir con la misma actividad que se elija para el ingreso (6120 / 6135). |

## Gastos

Categorías de gasto iniciales del sistema (RF-22):

| Categoría de gasto | Cuenta propuesta |
|---|---|
| Arriendo del local | 5120 Arrendamientos |
| Servicios públicos (agua, energía, gas) | 5135 Servicios |
| Internet y teléfono | 5135 Servicios |
| Transporte y fletes | 5135 Servicios |
| Honorarios (contador, asesorías) | 5110 Honorarios |
| Pagos a personal | 5105 Gastos de personal |
| Impuestos, licencias y permisos | 5115 Impuestos |
| Mantenimiento y reparaciones | 5145 Mantenimiento y reparaciones |
| Aseo y cafetería | 5195 Diversos |
| Papelería | 5195 Diversos |
| Publicidad | 5235 Servicios (gastos de ventas) |
| Comisiones y gastos bancarios | 5305 Financieros |
| Cortesías por su costo (RN-17, aprobado) | 5295 Diversos (gastos de ventas) |
| Mermas de inventario | 5295 Diversos, o dentro del costo de ventas (6140) |
| Otros gastos | 5195 Diversos |

## Dinero de terceros (no es ingreso)

| Concepto | Cuenta propuesta | Nota |
|---|---|---|
| Propinas (RN-15) | 2380 Acreedores varios | Se recibe y se entrega al personal. |
| Valor de domicilios (RN-18) | 2380 Acreedores varios | Se recibe y se liquida al domiciliario en el cierre de caja. |
| Abonos de encargos aún no entregados (RN-20) | 2805 Anticipos y avances recibidos | Pasan a ingreso el día de la entrega. |

## Preguntas para el contador

1. ¿Qué actividad (4120, 4135 o 4140) corresponde según el RUT?
2. ¿Quiere el reporte en cuentas de 4 dígitos o en subcuentas de 6?
3. ¿Las mermas van como gasto (5295) o dentro del costo de ventas?
4. ¿Las transferencias (Nequi, Bre-B, Bancolombia) se registran en 1110 Bancos o en otra cuenta?
