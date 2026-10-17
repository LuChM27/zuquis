# Propuesta de códigos PUC: para validar con el contador

Punto de partida para RF-22 y RF-43. Usa cuentas de 4 dígitos del PUC para comerciantes (Decreto 2650 de 1993). **Decidido el 17/10/2026:** actividad de elaboración de productos de panadería (4120 / 6120), reporte en cuentas de 4 dígitos, mermas como gasto aparte y transferencias que llegan a una mezcla de cuentas del negocio y personales. Falta que el contador dé el visto bueno a cada código. El sistema guarda el código como texto editable por categoría, así que cambiarlo no exige tocar código.

Se necesita validado antes de la fase 4 (reportes y exportación).

## Ingresos

| Concepto en el sistema | Cuenta propuesta | Nota para el contador |
|---|---|---|
| Ventas de productos (POS y encargos entregados) | 4120 Industrias manufactureras | Actividad del RUT: elaboración de productos de panadería. |
| Descuentos en ventas | 4175 Devoluciones en ventas (DB) | Se reportan aparte del ingreso bruto. |
| Abono retenido por cancelación de encargo (RN-22) | 4295 Diversos | Aprobado como ingreso aparte de las ventas. Es una excepción: por defecto se devuelve todo el abono. |

## Costo de ventas

| Concepto | Cuenta propuesta | Nota |
|---|---|---|
| Costo real PEPS de lo vendido | 6120 Industrias manufactureras | Misma actividad que el ingreso. |

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
| Mermas de inventario (gasto aparte, decidido el 17/10/2026) | 5295 Diversos |
| Otros gastos | 5195 Diversos |

## Dónde entra el dinero (métodos de pago)

Cada método de pago se configura con su titular y su cuenta, porque hay cuentas del negocio y cuentas personales de los dueños.

| Método | Titular | Cuenta propuesta | Nota |
|---|---|---|---|
| Efectivo | Negocio | 1105 Caja | |
| Transferencia a cuenta del negocio | Negocio | 1110 Bancos | Una por cada cuenta (Bancolombia, Nequi, Bre-B…) |
| Transferencia a cuenta personal de un dueño | Dueño | 1325 Cuentas por cobrar a socios y accionistas | Propuesta: el dinero es del negocio pero está en manos del socio. El contador puede preferir otro tratamiento |

## Dinero de terceros (no es ingreso)

| Concepto | Cuenta propuesta | Nota |
|---|---|---|
| Propinas (RN-15) | 2380 Acreedores varios | Se recibe y se entrega al personal. |
| Valor de domicilios (RN-18) | 2380 Acreedores varios | Se recibe y se liquida al domiciliario en el cierre de caja. |
| Abonos de encargos aún no entregados (RN-20) | 2805 Anticipos y avances recibidos | Pasan a ingreso el día de la entrega. |

## Preguntas para el contador

1. ¿Está de acuerdo con 4120 / 6120 para la actividad de elaboración de panadería?
2. ¿Cómo registra el dinero de ventas que llega a cuentas personales de los dueños? Propuesta: 1325.
3. ¿Da el visto bueno a los códigos de gastos y de dinero de terceros?
