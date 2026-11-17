# Caso de control · Fase 3: encargos y domicilios en dos días de caja

Calculado a mano. `tests/test_control_fase3.py` lo ejecuta por la API y debe coincidir al peso.
Si una regla cambia, se recalcula aquí primero y luego se ajusta la prueba.

**Reglas que intervienen**
- RN-18 · El valor del domicilio es del domiciliario: entra a la caja como `domicilio`, no suma
  en ventas y sale como `pago_domiciliario` al liquidar. Sin liquidar no se cierra la caja.
- RN-19 · Σ abonos ≤ total del encargo.
- RN-20 · Cada abono cuenta en la caja del día que se recibe; la venta, el día de la entrega.
- RN-21 · Al entregar se cobra solo el saldo; los abonos quedan aplicados a la venta.
- RN-22 · Al cancelar con devolución parcial, lo devuelto sale de la caja abierta
  (`devolucion_abono`) y lo retenido es ingreso por cancelación, no venta.

## Partida

- Vitrina (carta de pruebas): Pastel de pollo $4.500, lote de 12 a **$675**; Croissant de jamón
  y queso $7.500, lote de 8 a **$2.000**.
- Cliente A y Cliente B. Domiciliarios: Carlos y Diana.
- Métodos: Efectivo y Nequi. Cada día abre con base de **$100.000**.

## Día 1 (caja 1)

| # | Operación | Efectivo | Nequi |
|---|---|---|---|
| 1 | Encargo E1 (Cliente A): torta $90.000, **a domicilio**. Abono 1: $30.000 Nequi | | +30.000 |
| 2 | Encargo E2 (Cliente B): 24 cupcakes × $2.500 = $60.000. Abono: $40.000 efectivo | +40.000 | |
| 3 | Venta V1 a domicilio (Carlos): 2 pasteles $9.000 + domicilio $4.000, en efectivo | +13.000 | |
| 4 | Liquidación a Carlos: 1 domicilio | −4.000 | |

- Ventas del día 1: **$9.000** (solo V1; los abonos no son venta). Costo: 2 × $675 = **$1.350**.
- Abonos recibidos: 30.000 + 40.000 = **$70.000**.
- Esperado en efectivo: 100.000 + 40.000 + 9.000 + 4.000 − 4.000 = **$149.000**.
- Esperado en Nequi: **$30.000**.
- Saldos al cierre: E1 $60.000, E2 $20.000.

## Día 2 (caja 2)

| # | Operación | Efectivo | Nequi |
|---|---|---|---|
| 5 | E1: abono 2 de $20.000 en efectivo → saldo $40.000 | +20.000 | |
| 6 | E2 se cancela: de los $40.000 abonados se devuelven $25.000 en efectivo y se retienen $15.000 | −25.000 | |
| 7 | Venta V2 a domicilio (Diana): 1 croissant $7.500 + domicilio $5.000, por Nequi | | +12.500 |
| 8 | E1 pasa a producción, queda listo y se entrega a domicilio (Carlos): saldo $40.000 + domicilio $6.000, en efectivo → venta V3 | +46.000 | |
| 9 | Liquidación a Carlos: 1 domicilio | −6.000 | |
| 10 | Liquidación a Diana: 1 domicilio (se le entrega en efectivo aunque se cobró por Nequi) | −5.000 | |

- Ventas del día 2: V2 $7.500 + V3 $90.000 = **$97.500**. V3 lleva $50.000 de abonos aplicados y
  cobra $40.000 + $6.000 de domicilio = $46.000. Costo: croissant **$2.000**; la torta
  personalizada no descuenta inventario.
- En el resumen del turno: ventas cobradas hoy **$7.500**; abonos y saldos de encargos
  20.000 + 40.000 = **$60.000**; domicilios entregados **$11.000**.
- Ingreso por cancelación: **$15.000** (no es venta).
- Esperado en efectivo: 100.000 + 20.000 − 25.000 + 40.000 + 6.000 − 6.000 − 5.000 = **$130.000**.
- Esperado en Nequi: **$12.500**.

## Comprobación cruzada

- Encargo E1: 30.000 + 20.000 + 40.000 = 90.000 = total. ✔
- Encargo E2: 40.000 recibidos = 25.000 devueltos + 15.000 retenidos. ✔
- Domicilios: cobrados 4.000 + 5.000 + 6.000 = 15.000 = entregados 4.000 + 11.000. ✔
- Dinero neto de los dos días (sin bases): efectivo 49.000 + 30.000 = 79.000; Nequi 42.500;
  total **$121.500** = ventas 106.500 + ingreso por cancelación 15.000. ✔
- Vitrina al final: 10 pasteles y 7 croissants.
