# Mockups del sistema

Estos mockups son la **referencia visual obligatoria** del frontend. Las pantallas se construyen recreándolos tal como están: estructura, jerarquía, textos, colores, tipografía, espaciado y componentes. No son solo inspiración.

Si algo del mockup choca con la especificación (un dato que no existe en el modelo, un flujo distinto), se resuelve primero la discrepancia y luego se ajusta el mockup o la especificación; no se improvisa en el código. Las pantallas que no tienen mockup (login, compras, gastos, reportes, configuración, etc.) se diseñan siguiendo el mismo sistema visual de estas.

| Pantalla | Archivo | Qué fija |
|---|---|---|
| Inicio (dashboard) | [dashboard.png](dashboard.png) | Saludo + fecha/sede, 4 tarjetas de cifras, ventas por hora (barras, hora pico resaltada), cómo pagaron hoy (barras horizontales), más vendidos, encargos para hoy, alertas de inventario, chip "Datos de ejemplo", botón "Nueva venta" |
| Vender (POS, escritorio) | [pos-escritorio.png](pos-escritorio.png) | Buscador, categorías en píldoras, tarjetas de producto con ícono, precio y estado ("Se prepara" / "N en vitrina" en verde o rojo), panel de venta con tipo de servicio (En local / Para llevar / Domicilio), líneas con −/+ y notas, subtotal, descuento, propina aparte, total a cobrar, pago mixto por método, botón "Cobrar" |
| Vender (POS, celular) | [pos-celular.png](pos-celular.png) | Cabecera rosa con logo, título y estado de caja, menú hamburguesa, categorías con scroll horizontal, tarjetas en 2 columnas sin ícono con contador de cantidad, barra inferior fija "N productos · tipo · total / Ver y cobrar" |
| Cierre de caja | [cierre-caja.png](cierre-caja.png) | Pasos (1 Liquidar domicilios, 2 Contar el dinero, 3 Confirmar y cerrar), domicilios del turno, arqueo por método (debería haber / contado / diferencia), observación obligatoria si hay diferencia, de dónde sale el efectivo, resumen del turno |
| Inventario por lotes | [inventario.png](inventario.png) | Botones registrar merma / producción / compra, 4 tarjetas (valor, bajo el mínimo en rojo, por vencer en amarillo, mermas), pestañas Insumos / Productos en vitrina / Movimientos, tabla con estado (Bajo el mínimo, Por vencer, Bien), panel de detalle con lotes PEPS ("Se usa primero", "Siguiente") y recetas que lo usan |
| Encargos y abonos | [encargos.png](encargos.png) | Semana en tarjetas por día (hoy resaltado), lista del día con hora, cliente, entrega, saldo y estado, panel de detalle con progreso de estados (Pendiente → En producción → Listo → Entregado), abonos, saldo por cobrar, aviso de bloqueo de edición, "Entregar y cobrar" y "Registrar otro abono" |

## Sistema visual que se desprende de los mockups

- **Marco:** sidebar rosa con logo + "ZUQUI'S / REPOSTERÍA", navegación con íconos de línea (Inicio, Vender, Caja, Encargos, Inventario, Compras, Gastos, Reportes, Configuración); ítem activo en tarjeta crema con borde dorado. Abajo, tarjeta de estado de caja (punto verde, "Caja abierta desde 3:00 p. m.") con el rol del usuario.
- **Área de trabajo:** fondo crema; encabezado con línea de contexto pequeña arriba (fecha, sede, semana) y título grande en serif; acciones a la derecha.
- **Tarjetas:** fondo blanco/crema, borde dorado claro de 1 px, esquinas muy redondeadas. Tarjetas de alerta con fondo rosado (peligro) o amarillo claro (advertencia). Los paneles de detalle laterales llevan borde dorado más marcado.
- **Tipografía:** títulos y cifras grandes en serif (tipo Cormorant Garamond, con números de estilo antiguo); texto, tablas y botones en sans (tipo Montserrat). Encabezados de tabla en versalitas con espaciado.
- **Botones:** principal fucsia con texto blanco en negrita; secundario blanco con borde dorado; píldoras de filtro con la activa en fucsia.
- **Estados (chips):** verde "Bien/Entregado", rojo "Bajo el mínimo", amarillo "Por vencer/En producción", rosa "Listo", neutro "Pendiente". Diferencias de dinero en rojo (negativas) y verde ($0).
- **Montos:** `$684.500`, alineados a la derecha; los negativos con signo `−` en rojo.
