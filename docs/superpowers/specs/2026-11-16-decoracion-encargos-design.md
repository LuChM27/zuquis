# Decoración en encargos — diseño

Fecha: 2026-11-16 · Estado: pendiente de aprobación

## Por qué

Muchos encargos son tortas (u otros productos) con decoración que se cotiza según lo que pida el
cliente. Hoy, para cobrar la decoración, hay que volver el producto un ítem personalizado, y así
pierde su receta y no descuenta inventario. Se quiere: el producto de la carta con su precio
estándar (p. ej. Torta 1 lb $110.000) y la decoración como agregado aparte. Además, saber cuánto
se gastó en materiales de decoración por encargo y en total.

## Metas

1. Cada ítem del encargo puede llevar **una decoración opcional**: referencia (texto libre, qué
   decoración es) y valor (a mano). Solo en encargos; el POS no cambia.
2. La decoración **suma al total** del encargo y **no toca inventario**.
3. Al entregar, la venta lleva la decoración como **línea propia** debajo del producto.
4. Desde el encargo se registran **gastos de materiales de decoración**, ligados a él, con la
   categoría nueva **"Materiales de decoración"**; cuentan en los gastos generales como cualquier
   otro.
5. El detalle del encargo muestra: decoración cobrada, gastado en materiales y diferencia.

## No metas

- Lista o catálogo de decoraciones con precio fijo (cada una se cotiza).
- Insumos o receta para la decoración (los materiales se compran aparte, no van al inventario).
- Varias decoraciones por ítem (se escriben juntas en la referencia).
- Cambios al POS.

## Enfoques considerados

- **A. Decoración dentro del ítem** (elegido): dos campos opcionales en el ítem del encargo.
  Simple, se ve pegado al producto en el formulario.
- **B. Decoración como sub-ítems**: varias líneas por producto. Descartado: formulario más pesado
  y cambio de modelo mayor para un caso raro.

## Diseño

**Base de datos (migración Alembic)**
- `encargo_items`: `decoracion` (String 200, nullable) y `decoracion_precio` (pesos, nullable,
  ≥ 0). Ambos o ninguno (check constraint).
- `gastos`: `encargo_id` (FK a `encargos`, nullable, indexada).
- Categoría "Materiales de decoración" (PUC 5195) agregada a `CATEGORIAS_INICIALES` y creada por
  la migración en las sedes existentes.

**Reglas**
- Total del encargo = Σ (cantidad × precio) + Σ decoracion_precio. La decoración es un valor por
  ítem, no por unidad.
- El precio del producto se precarga con el de la carta y sigue siendo editable (como hoy).
- Decoración permitida en ítems de la carta y personalizados.
- Editar el encargo permite cambiar o quitar la decoración mientras esté editable (mismas reglas
  que los ítems). Si el total baja de lo abonado aplica la validación existente.
- Al entregar: la venta incluye, después de cada línea con decoración, una línea sin producto
  "Decoración: <referencia>" con cantidad 1 y su valor. No descuenta inventario.
- Gasto de decoración: `POST /encargos/{id}/gastos` con monto, descripción, método de pago y
  fuente (caja / banco / dueños); reutiliza el servicio de gastos con la categoría fija y
  `encargo_id`. Se permite en cualquier estado del encargo, también antes de entregarlo; si el
  encargo se cancela, los gastos se quedan. Se anulan desde Gastos como cualquier otro.
- Resumen en la salida del encargo: `decoracion_cobrada`, `gasto_decoracion` (solo gastos no
  anulados), y lista de esos gastos.

**Frontend**
- `FormEncargo`: en cada ítem, botón "＋ Decoración" que despliega Referencia y Valor; botón para
  quitarla. El total la incluye.
- Panel de detalle: líneas de decoración bajo cada ítem; bloque "Decoración" con cobrado, gastado
  y diferencia; botón "Registrar gasto de decoración" (formulario corto: monto, qué se compró,
  de dónde sale la plata).
- Gastos: la categoría nueva aparece sola; el gasto muestra el encargo al que pertenece.

**Pruebas**
- Backend: total con decoración; entrega crea la línea de decoración sin mover inventario;
  gasto ligado aparece en el encargo y en la lista de gastos; anulado no cuenta; cancelación
  conserva gastos.
- E2E: crear encargo con decoración, registrar gasto, entregar y ver el comprobante.

## Queda a criterio del implementador

- Textos exactos y orden visual dentro del panel, siguiendo el estilo del mockup de encargos.
- Dónde vive el endpoint (módulo encargos llamando a gastos) mientras no duplique reglas.

## Rama

Se trabaja en `fase-3` y entra en el PR #61 (sigue abierto y es el mismo módulo).
