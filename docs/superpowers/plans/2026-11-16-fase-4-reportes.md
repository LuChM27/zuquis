# Fase 4 — Reportes, dashboard y galería: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dashboard de Inicio, reportes por rango exportables a Excel/PDF con reporte PUC, galería de 14 gráficos en Reportes y caso de control de una semana que cuadra al peso.

**Architecture:** Módulo backend `reportes` sin tablas propias. Una capa de **cifras** (`cifras.py`) agrega en SQL y es la única fuente de cada número. Reportes en tablas, dashboard, gráficos y exportación se arman encima de ella. Cada reporte es un `Reporte` genérico (secciones con columnas tipadas), así que una sola rutina lo convierte en JSON, Excel o PDF. En el frontend, ECharts va envuelto en un componente propio con un tema de marca y se carga en diferido.

**Tech Stack:** FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, openpyxl (nuevo), WeasyPrint · React 19, TanStack Query, Tailwind 4, echarts (nuevo), Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-16-fase-4-reportes-design.md`. Leerlo antes de cada tarea. Las definiciones de cifras de su §4.1 mandan.

## Global Constraints

- Rama `fase-4`. Un commit por tarea, en español, con estilo `feat(reportes): … (#46)`.
- Dinero en `int` (pesos). Costos `Decimal`. Porcentajes `Decimal` serializados como string. **Cero float** en backend y en respuestas JSON. En el frontend, los porcentajes se leen con `decimal.js` (`lib/decimal.ts`).
- Fechas: los rangos `desde`/`hasta` son fechas locales `America/Bogota`, con `hasta` inclusive. Se usa `zona()` de `app/shared/fechas.py`.
- Capas: `router.py` valida y autoriza; la lógica vive en el módulo. Los permisos se validan en el backend con `requiere`/`requiere_alguno` de `app/core/deps.py`.
- Permisos existentes: `reportes.ver`, `reportes.ver_caja_propia`, `reportes.ver_inventario`, `reportes.exportar`.
- Interfaz en español, `$12.500`, `dd/mm/aaaa`, montos alineados a la derecha. Las pantallas siguen `docs/mockups/` (Inicio = `dashboard.png` tal cual).
- Colores siempre desde los tokens de `frontend/src/styles.css` (`--color-fucsia #c42d72`, `--color-rosa-barra #f2a9c6`, `--color-dorado #b08d3c`, …).
- Pruebas backend: `cd backend && pytest` contra PostgreSQL de pruebas (`zuquis_test`). Frontend: `cd frontend && npm test -- --run`, `npm run lint`, `npm run build`.
- Los cálculos esperados de las pruebas de control se escriben a mano. Nunca se calculan con las funciones que se están probando.

## Review Focus

1. **Rango sin datos:** todos los reportes, gráficos y el dashboard devuelven ceros y listas vacías, no un 500. Los porcentajes y el ticket promedio con denominador 0 dan `"0"`, no una división por cero. Prueba en la Tarea 2 (`test_rango_vacio_da_ceros`) y en la Tarea 6 (`test_grupos_vacios`).
2. **Lo anulado no cuenta:** ventas, gastos, abonos y compras anuladas, y producciones anuladas, no suman en ninguna cifra. Prueba en la Tarea 2 (`test_anuladas_no_suman`) y en la Tarea 3 (`test_gasto_anulado_no_suma`).
3. **Medianoche en Bogotá:** una venta a las 23:30 hora local cae en ese día y no en el siguiente (UTC), y su hora en el mapa de calor es 23. Prueba en la Tarea 2 (`test_venta_2330_cae_en_su_dia_local`).
4. **Rangos inválidos:** `desde > hasta` → 422 con el mensaje "La fecha inicial no puede ser posterior a la final". Un rango de más de 366 días → 422 "El rango no puede pasar de un año". Prueba en la Tarea 2 (`test_rango_invalido`).
5. **Otra sede:** `sede_id` de una sede donde el usuario no tiene `reportes.ver` → 403. Prueba en la Tarea 2 (`test_sede_ajena_403`).

---

### Task 1: Compras con fecha límite de pago opcional

**Files:**
- Create: `backend/migrations/versions/20261116_0009_fase_4_fecha_limite_pago.py`
- Modify: `backend/app/modules/compras/models.py`, `schemas.py`, `service.py`
- Modify: `frontend/src/pages/compras/NuevaCompra.tsx`, `frontend/src/pages/compras/PorPagar.tsx`
- Test: `backend/tests/test_compras.py`

**Interfaces:**
- Produces: columna `compras.fecha_limite_pago DATE NULL`; `CompraCrear.fecha_limite_pago: date | None = None`; `CompraSalida.fecha_limite_pago` y `CuentaPorPagar.fecha_limite_pago: date | None`.

- [ ] **Step 1: Pruebas que fallan** en `test_compras.py`:
  - `test_compra_a_credito_guarda_fecha_limite`: crear una compra por pagar con `fecha_limite_pago="2026-12-15"`. La respuesta y `GET /cuentas-por-pagar` la devuelven.
  - `test_fecha_limite_es_opcional`: una compra por pagar sin el campo responde 201 con `fecha_limite_pago is None`.
  - `test_fecha_limite_en_compra_de_contado_se_rechaza`: compra de contado con el campo → 422, con un mensaje que contiene "solo aplica a compras por pagar".
- [ ] **Step 2:** `pytest tests/test_compras.py -k fecha_limite -v` → FAIL.
- [ ] **Step 3:** Migración `0009` (`down_revision` = revisión de `0008`). Agregar el campo al modelo, los esquemas y `crear_compra`. La validación del caso de contado va en `crear_compra` con el error de dominio que ya usa el módulo.
- [ ] **Step 4:** `pytest tests/test_compras.py -v` → PASS.
- [ ] **Step 5: Frontend.** En `NuevaCompra.tsx`, el campo de fecha "Pagar antes del" solo aparece cuando la compra queda por pagar, no es obligatorio y se envía como `aaaa-mm-dd`. En `PorPagar.tsx`, una columna "Pagar antes del" que dice "Sin fecha" cuando está vacía y muestra un `Chip tono="peligro"` "Vencida" si la fecha ya pasó (`fecha < hoy` en Bogotá).
- [ ] **Step 6:** `npm test -- --run && npm run lint` → PASS.
- [ ] **Step 7: Commit** `feat(compras): fecha límite de pago opcional en compras a crédito`.

---

### Task 2: Base del módulo `reportes`, cifras de ventas y reporte de ventas

**Files:**
- Create: `backend/app/modules/reportes/__init__.py`, `periodo.py`, `esquemas.py`, `cifras.py`, `tablas.py`, `router.py`
- Create: `backend/migrations/versions/20261116_0010_fase_4_indices_reportes.py`
- Modify: `backend/app/main.py` (registrar el router), `backend/app/shared/fechas.py` (reloj fijo)
- Create: `backend/tests/test_reportes_ventas.py`, `backend/tests/fixtures_reportes.py` (agregarlo a `pytest_plugins` en `conftest.py`)

**Interfaces:**
- Produces (`app/shared/fechas.py`): `fijar_ahora(momento: datetime | None) -> None`. `ahora()` devuelve ese momento si está fijado. Así funciona en todos los módulos que hicieron `from app.shared.fechas import ahora` sin tener que parchearlos. Fixture `reloj` en `fixtures_reportes.py`: `reloj("2026-11-09T15:00:00-05:00")` fija la hora, y se libera al terminar la prueba. **Verificar** que ninguna columna de fecha usada en reportes dependa de `server_default=now()`. Si alguna depende, el servicio debe pasarle `ahora()` explícitamente.
- Produces (`periodo.py`):
  ```python
  @dataclass(frozen=True)
  class Periodo:
      sede_id: uuid.UUID
      desde: date
      hasta: date            # inclusive
      caja_sesion_id: uuid.UUID | None = None   # solo para reportes.ver_caja_propia
      def limites(self) -> tuple[datetime, datetime]: ...  # [inicio local, día siguiente a hasta local)
  def resolver_periodo(db, ctx, desde: date | None, hasta: date | None, sede_id: uuid.UUID | None) -> Periodo
  ```
  Por defecto: hoy..hoy y la sede del contexto. Errores: 422 si `desde > hasta` o si el rango pasa de 366 días (textos en Review Focus). 403 (`SinPermiso`) si `sede_id` es otra sede y `permisos_en_sede(db, ctx.usuario_id, sede_id)` no incluye `reportes.ver`.
- Produces (`esquemas.py`):
  ```python
  TipoColumna = Literal["texto", "pesos", "cantidad", "porcentaje", "fecha", "entero"]
  class Columna(BaseModel): clave: str; titulo: str; tipo: TipoColumna
  class Seccion(BaseModel): titulo: str; columnas: list[Columna]; filas: list[dict[str, Any]]; totales: dict[str, Any] | None = None
  class Reporte(BaseModel): tipo: str; titulo: str; sede: str; desde: date; hasta: date; generado_en: datetime; secciones: list[Seccion]
  ```
  `pesos` e `entero` son `int`; `cantidad` y `porcentaje` son `Decimal` serializados como string (usar el serializador de `app/shared/dinero.py`).
- Produces (`cifras.py`). Todo se agrega en SQL y todo filtra por `periodo.sede_id` y `limites()`:
  ```python
  class Totales(BaseModel):
      ventas: int; n_ventas: int; costo_insumos: int; costo_cortesias: int; n_cortesias: int
      descuentos: int; propinas: int; domicilios: int; gastos: int; mermas: int
      ingresos_cancelacion: int; anuladas: int
  def totales(db, p: Periodo) -> Totales
  AgrupaVentas = Literal["dia", "semana", "hora", "dia_semana_hora", "producto", "categoria", "metodo", "servicio", "cajero"]
  class FilaVentas(BaseModel): clave: str; etiqueta: str; ventas: int; costo: int; unidades: Decimal; n: int
  def ventas_por(db, p: Periodo, por: AgrupaVentas) -> list[FilaVentas]
  ```
  Definiciones: las de spec §4.1. Una cortesía se reconoce por `subtotal > 0 AND total = 0`. `costo_insumos` excluye cortesías y `costo_cortesias` las suma. `descuentos = SUM(descuento_total)` de las pagadas, cortesías incluidas. `"dia"` usa como clave `aaaa-mm-dd` local. `"semana"` usa la semana ISO `aaaa-Www`. `"hora"` va de `0` a `23` local. `"dia_semana_hora"` usa `"<isodow>-<hora>"`. `"metodo"` suma `venta_pagos.monto` (no `total`). `"producto"` suma `venta_items` con el nombre como en `ventas/service.py::resumen` (decoración e ítems libres). `"categoria"` agrupa por la categoría de la carta del producto, y los ítems sin producto van a "Sin categoría". `"cajero"` agrupa por `ventas.usuario_id` con el nombre del usuario. `gastos`, `mermas` e `ingresos_cancelacion` se calculan en `totales()` con las definiciones de spec §4.1. Si `p.caja_sesion_id` viene, las ventas se filtran por esa sesión.
- Produces (`tablas.py`): `def reporte_ventas(db, p: Periodo) -> Reporte`. Secciones: "Resumen" (los `Totales` relevantes, una fila por concepto), "Por día", "Por producto", "Por categoría", "Por método de pago", "Por tipo de servicio" y "Por cajero", cada una con totales al pie.
- Produces (`router.py`): `GET /reportes/{tipo}` con `desde`, `hasta`, `sede_id` y `formato: Literal["json","xlsx","pdf"]="json"`. Por ahora solo `tipo="ventas"`, y un `tipo` desconocido → 404. La autorización por tipo vive en un diccionario `ACCESO: dict[str, frozenset[str]]` (tipo → permisos que lo abren), con `ventas: {reportes.ver, reportes.ver_caja_propia}`. Si el usuario solo tiene `ver_caja_propia`, el `Periodo` lleva la `caja_sesion_id` de la caja abierta de su sede, y si no hay caja abierta responde con un reporte vacío.
- Índices (migración 0010): crear, solo si no existen (consultar `pg_indexes` dentro de la migración o usar `postgresql_if_not_exists`), índices `(sede_id, fecha)` en `ventas`, `gastos`, `caja_movimientos`, `mermas`, `movimientos_inventario`, `producciones`, `encargo_abonos`, y `(sede_id, cancelado_en)`, `(sede_id, entregado_en)` en `encargos`.

- [ ] **Step 1: Pruebas que fallan** en `test_reportes_ventas.py`, usando las fixtures `carta`, `metodos`, `caja_abierta` y `vender` de `fixtures_ventas.py`:
  - `test_totales_de_un_dia`: dos ventas (una con propina 2.000 y descuento 1.000) y una cortesía. Assert de cada campo de `Totales` contra valores escritos a mano. `costo_insumos` no incluye el costo de la cortesía y `costo_cortesias` sí.
  - `test_anuladas_no_suman`: anular una venta. `totales().ventas` no la incluye y `anuladas == 1`.
  - `test_venta_2330_cae_en_su_dia_local`: con `reloj("2026-11-10T23:30:00-05:00")` vender. `ventas_por(..., "dia")` devuelve la clave `"2026-11-10"` y `ventas_por(..., "hora")` devuelve la clave `"23"`.
  - `test_por_metodo_suma_pagos`: un pago mixto Efectivo 10.000 + Nequi 5.000 → dos filas con esos montos.
  - `test_rango_vacio_da_ceros`: `GET /reportes/ventas?desde=2020-01-01&hasta=2020-01-02` → 200, el resumen en cero y las secciones sin filas.
  - `test_rango_invalido`: `desde>hasta` → 422 con su texto, y 400 días → 422 con su texto.
  - `test_sede_ajena_403`.
  - `test_permisos_ventas`: un usuario de producción → 403. Un cajero ve solo las ventas de la caja abierta.
- [ ] **Step 2:** `pytest tests/test_reportes_ventas.py -v` → FAIL.
- [ ] **Step 3:** Implementar `fijar_ahora`, `periodo.py`, `esquemas.py`, `cifras.py`, `tablas.reporte_ventas`, `router.py` y la migración `0010`. Registrar el router en `main.py` igual que los demás.
- [ ] **Step 4:** `pytest tests/test_reportes_ventas.py -v` → PASS. Luego `pytest` completo → PASS. Esto incluye la guardia anti-Float y las migraciones.
- [ ] **Step 5: Commit** `feat(reportes): base del módulo, cifras de ventas y reporte de ventas (#46)`.

---

### Task 3: Reportes de dinero

**Files:**
- Modify: `backend/app/modules/reportes/cifras.py`, `tablas.py`, `router.py`
- Test: `backend/tests/test_reportes_dinero.py`

**Interfaces:**
- Consumes: `Periodo`, `Reporte`, `totales`, `ventas_por` (Tarea 2).
- Produces (`cifras.py`):
  ```python
  class FilaGasto(BaseModel): categoria: str; cuenta_puc: str | None; fuente: str; mes: str; monto: int; n: int
  def gastos_por(db, p) -> list[FilaGasto]                       # sin anulados, por gastos.fecha
  class FilaFlujo(BaseModel): dia: str; tipo: str; metodo: str; titular: str; en_caja: bool; entra: int; sale: int
  def flujo(db, p) -> list[FilaFlujo]
  class FilaCierre(BaseModel): sesion_id: uuid.UUID; abierta_en: datetime; cerrada_en: datetime; cerrada_por: str; metodo: str; esperado: int; contado: int; diferencia: int
  def cierres(db, p) -> list[FilaCierre]                         # por cerrada_en en el rango
  def descuentos_cortesias(db, p) -> list[dict]                  # venta, fecha, cajero, motivo, autorizó, descuento, es_cortesia, costo
  def domicilios_por(db, p) -> list[dict]                        # domiciliario, n, valor
  def propinas_por_dia(db, p) -> list[dict]                      # dia, propinas
  def cancelaciones(db, p) -> list[dict]                         # encargo, cliente, cancelado_en, devuelto, retenido, motivo
  ```
  Flujo: `caja_movimientos` (`en_caja=True`; signo según tipo: entran `venta, propina, domicilio, abono, saldo_encargo, entrada_manual`, salen `pago_domiciliario, devolucion_abono, gasto, pago_compra, salida_manual`, y `reverso_anulacion` con el signo que tenga su monto. **Verificar en `caja/service.py`** cómo se guarda), **más** gastos sin `caja_sesion_id` y `pagos_compra` sin `caja_sesion_id` (`en_caja=False`, tipo `gasto` / `pago_compra`). `titular` sale de `metodos_pago.titular`.
- Produces (`tablas.py`): `reporte_gastos`, `reporte_flujo_caja` (secciones "Por día", "Por tipo", "Por titular" con negocio/dueño, "Fuera de caja"), `reporte_propinas`, `reporte_domicilios`, `reporte_descuentos_cortesias`, `reporte_ingresos_cancelacion` y `reporte_cierres`. Las firmas son `(db, p) -> Reporte`. Se registran en `router.py` con los tipos `gastos, flujo-caja, propinas, domicilios, descuentos-cortesias, ingresos-cancelacion, cierres`, todos con `{reportes.ver}`, y `cierres` también con `reportes.ver_caja_propia` (limitado a su caja).

- [ ] **Step 1: Pruebas que fallan**, con valores a mano:
  - `test_gastos_por_categoria_y_fuente`: un gasto de caja de 20.000 y uno del banco de 50.000 → dos filas y total 70.000.
  - `test_gasto_anulado_no_suma`.
  - `test_flujo_incluye_fuera_de_caja_sin_duplicar`: una venta en efectivo de 10.000, un gasto de caja de 3.000 y un gasto del banco de 5.000 → entra 10.000. Sale 8.000, de lo que 5.000 es `en_caja=False`. El gasto de caja aparece una sola vez.
  - `test_flujo_por_titular`: un método con `titular="dueno"` recibe 7.000 → la sección "Por titular" muestra dueño 7.000.
  - `test_cierre_con_diferencia_asignada_a_quien_cerro`.
  - `test_ingreso_por_cancelacion_por_fecha_de_cancelacion`, usando `crear_encargo`, `abonar` y `cancelar` de `fixtures_encargos.py`, con retención de 15.000.
  - `test_descuento_registra_quien_autorizo`.
- [ ] **Step 2:** `pytest tests/test_reportes_dinero.py -v` → FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** `pytest tests/test_reportes_dinero.py -v` → PASS.
- [ ] **Step 5: Commit** `feat(reportes): gastos, flujo de caja, propinas, domicilios, descuentos, cancelaciones y cierres (#46)`.

---

### Task 4: Reportes de inventario y utilidad

**Files:**
- Modify: `backend/app/modules/reportes/cifras.py`, `tablas.py`, `router.py`
- Test: `backend/tests/test_reportes_inventario.py`

**Interfaces:**
- Produces (`cifras.py`):
  ```python
  class FilaUtilidad(BaseModel): producto: str; unidades: Decimal; ventas: int; costo: int; utilidad: int; margen: Decimal  # margen = utilidad/ventas, "0" si ventas=0
  def utilidad_por_producto(db, p) -> list[FilaUtilidad]          # desde venta_items (sin cortesías), modificadores incluidos en el costo
  class FilaValorizado(BaseModel): tipo_item: str; item: str; lote_id: uuid.UUID; fecha_ingreso: date; cantidad: Decimal; costo_unitario: Decimal; valor: int
  def inventario_valorizado(db, sede_id, corte: date) -> list[FilaValorizado]
  class FilaMerma(BaseModel): motivo: str; tipo_item: str; item: str; cantidad: Decimal; costo: int
  def mermas_por(db, p) -> list[FilaMerma]
  class FilaProducido(BaseModel): producto: str; producido: Decimal; vendido: Decimal
  def producido_vs_vendido(db, p) -> list[FilaProducido]           # producciones no anuladas vs salidas de inventario por venta de ese producto
  ```
  Inventario valorizado: por lote, cantidad = `SUM(movimientos_inventario.cantidad)` con `fecha < día siguiente al corte` (verificar en `inventario/motor.py` el signo de las salidas). Se omiten los lotes en 0. `valor` = cantidad × `costo_unitario` del lote, redondeado una sola vez por lote con `ROUND_HALF_UP` (usar `app/shared/dinero.py`).
- Produces (`tablas.py`): `reporte_utilidad_productos`, `reporte_inventario_valorizado` (usa `p.hasta` como corte), `reporte_mermas`. `ACCESO`: `utilidad-productos: {reportes.ver}`, `inventario-valorizado` y `mermas: {reportes.ver, reportes.ver_inventario}`.

- [ ] **Step 1: Pruebas que fallan:**
  - `test_utilidad_por_producto`: una venta de 2 brownies → ventas, costo PEPS y margen (`Decimal`, string en JSON) a mano.
  - `test_valorizado_a_fecha_pasada`: comprar 10 u. a $1.000 el día 1 (con `reloj`), consumir 4 el día 3. El corte del día 2 vale 10.000 y el corte del día 3 vale 6.000.
  - `test_mermas_por_motivo`.
  - `test_produccion_ve_inventario_pero_no_utilidad`: el rol producción recibe 200 en `mermas` y 403 en `utilidad-productos`.
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** `pytest tests/test_reportes_inventario.py -v` → PASS.
- [ ] **Step 5: Commit** `feat(reportes): utilidad por producto, inventario valorizado y mermas (#46)`.

---

### Task 5: Endpoint del dashboard y marca "Datos de ejemplo"

**Files:**
- Create: `backend/app/modules/reportes/dashboard.py`
- Modify: `backend/app/modules/reportes/router.py`, `backend/app/modules/configuracion/schemas.py` (clave `datos_ejemplo`)
- Test: `backend/tests/test_reportes_dashboard.py`

**Interfaces:**
- Produces:
  ```python
  class EncargoHoy(BaseModel): id: uuid.UUID; numero: int; descripcion: str; cliente: str; hora: datetime; saldo: int; estado: str
  class Dashboard(BaseModel):
      fecha: date; caja_abierta_desde: datetime | None; datos_ejemplo: bool
      ventas: int; n_ventas: int; gastos: int; n_gastos: int; ganancia: int; ticket_promedio: int
      por_hora: list[FilaVentas]; por_metodo: list[FilaVentas]; porcentaje_metodo: dict[str, Decimal]
      mas_vendidos: list[FilaVentas]   # top 5 por unidades
      encargos_hoy: list[EncargoHoy]; alertas: list[Alerta]   # Alerta de inventario/schemas.py
  def dashboard(db, ctx) -> Dashboard
  ```
  Periodo: desde la fecha local de apertura de la caja abierta de la sede hasta hoy, o hoy..hoy si no hay caja abierta. `ganancia = ventas − costo_insumos − costo_cortesias − gastos` (la tarjeta del mockup dice "ventas menos costo real de insumos y gastos"). `ticket_promedio = ventas // (n_ventas − n_cortesias)`, con 0 si el divisor es 0 y redondeo `ROUND_HALF_UP`. Encargos de hoy: `fecha_entrega` hoy y estado distinto de cancelado o entregado, ordenados por hora, con `saldo = total − abonado` (reusar `encargos.service.abonado`). Alertas: `inventario.consultas.alertas(db, ctx)`. Clave `"datos_ejemplo": (TypeAdapter(bool), False)` en `CLAVES`. `GET /reportes/dashboard` con `requiere("reportes.ver")`.

- [ ] **Step 1: Pruebas que fallan:**
  - `test_dashboard_igual_al_reporte_del_dia`: misma data que `test_totales_de_un_dia`. `ventas`, `n_ventas` y `por_metodo` son iguales a `GET /reportes/ventas` del mismo día (criterio de aceptación de #45).
  - `test_ganancia_y_ticket`: valores a mano, con cortesía incluida.
  - `test_encargos_hoy_con_saldo`.
  - `test_sin_caja_ni_datos`: todo en 0 y sin división por cero.
  - `test_datos_ejemplo_lee_la_configuracion`.
  - `test_cajero_no_ve_dashboard` → 403.
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(reportes): endpoint del dashboard (#45)`.

---

### Task 6: Endpoint de la galería de gráficos

**Files:**
- Create: `backend/app/modules/reportes/graficos.py`
- Modify: `backend/app/modules/reportes/cifras.py` (lo que falte), `router.py`
- Test: `backend/tests/test_reportes_graficos.py`

**Interfaces:**
- Consumes: todas las funciones de `cifras.py` de las Tareas 2–4. **No hay consultas nuevas que repitan una cifra.** Solo se agregan a `cifras.py` las que no existen:
  ```python
  def por_pagar(db, sede_id, corte: date) -> list[dict]    # compra, proveedor, fecha, fecha_limite_pago, saldo
  def encargos_por_semana(db, p) -> list[dict]             # semana, entregados, cancelados
  def abonos_sin_entregar(db, sede_id, corte: date) -> int # abonos vigentes con fecha <= corte de encargos no entregados ni cancelados a esa fecha
  def clientes_top(db, p, n=10) -> list[dict]              # cliente, encargos, total (encargos entregados en el rango)
  def por_cajero(db, p) -> list[dict]                      # cajero, vendido, descuentos, cortesias, diferencia_cierres (por cerrada_por)
  ```
- Produces:
  ```python
  Grupo = Literal["ganancia", "ventas", "productos", "gastos", "encargos", "cajeros"]
  def grupo(db, p: Periodo, g: Grupo) -> dict[str, Any]    # claves fijas por grupo (abajo)
  ```
  `GET /reportes/graficos?grupo=&desde=&hasta=&sede_id=`. Claves de respuesta:
  - `ganancia`: `cascada` {ventas, costo_insumos, regalado, gastos, mermas, ingresos_cancelacion, utilidad}; `costo_pct` [{semana, ventas, costo, pct}]; `flujo` [{dia, entra_negocio, entra_dueno, sale}].
  - `ventas`: `dia_a_dia` [{dia, ventas}] + `anterior` [{dia, ventas}] (el periodo previo del mismo largo); `calor` [{dow 1-7, hora 0-23, ventas}]; `categorias` [{categoria, ventas, pct}].
  - `productos`: `mas_vendidos` (top 10 por unidades), `menos_vendidos` (los 10 productos **activos** de la carta con menos unidades, incluidos los de 0); `producido_vendido`.
  - `gastos`: `por_categoria_mes` [{mes, categoria, monto}]; `mermas` [{motivo, costo}] + [{item, costo}]; `por_pagar` {con_fecha: {vencidas, esta_semana, proximas}, sin_fecha: {d0_15, d16_30, d30_mas}} con el corte en `p.hasta`.
  - `encargos`: `por_semana`; `abonos_sin_entregar`; `clientes_top`.
  - `cajeros`: `por_cajero`.
  `utilidad = ventas − costo_insumos − regalado − gastos − mermas + ingresos_cancelacion`. Acceso: `reportes.ver` para todos los grupos. Con solo `reportes.ver_inventario`, el grupo `productos` devuelve únicamente `producido_vendido`, el grupo `gastos` únicamente `mermas`, y el resto → 403.

- [ ] **Step 1: Pruebas que fallan:**
  - `test_cascada_cuadra_con_reportes`: `cascada.ventas == reporte ventas`, `cascada.gastos == total de reporte gastos` y `utilidad` es igual al valor a mano.
  - `test_calor_en_hora_local`.
  - `test_menos_vendidos_incluye_productos_sin_ventas`.
  - `test_por_pagar_con_y_sin_fecha`: una compra con fecha límite vencida (30.000) y una sin fecha de hace 20 días (12.000) → `vencidas=30000` y `d16_30=12000`.
  - `test_abonos_sin_entregar_a_la_fecha`.
  - `test_grupos_vacios`: los 6 grupos en un rango sin datos → 200 con ceros.
  - `test_sin_floats_en_respuestas`: recorrer recursivamente el JSON de los 6 grupos, del dashboard y de cada tipo de reporte. Ningún valor es `float` (los porcentajes llegan como `str`).
  - `test_produccion_solo_ve_lo_suyo`.
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat(reportes): datos de la galería de gráficos`.

---

### Task 7: Excel, PDF, precarga PUC y reporte PUC

**Files:**
- Create: `backend/app/modules/reportes/exportar.py`, `backend/app/modules/reportes/puc.py`
- Create: `backend/migrations/versions/20261116_0011_fase_4_precarga_puc.py`
- Modify: `backend/pyproject.toml` (`openpyxl>=3.1`), `router.py`
- Test: `backend/tests/test_reportes_exportar.py`

**Interfaces:**
- Produces:
  ```python
  def a_xlsx(r: Reporte, negocio: str) -> bytes
  def a_pdf(r: Reporte, negocio: str) -> bytes            # usa app/shared/pdf.py: pagina(), pesos(), logo_data_uri()
  def reporte_puc(db, p) -> Reporte                       # tipo "puc"
  ```
  Excel: una hoja por sección (nombre ≤ 31 caracteres, sin `[]:*?/\`). Las filas 1–4 llevan el encabezado: negocio, sede, "Del dd/mm/aaaa al dd/mm/aaaa" y "Generado el dd/mm/aaaa h:mm". Las columnas `pesos` se escriben como `int` con `number_format = '"$"#,##0'`. `cantidad` y `porcentaje` van como `Decimal` exacto (porcentaje con formato `0.00%` sobre el valor/100). La fila de totales usa `=SUM(...)`. PDF: el mismo encabezado y una tabla por sección, con la línea visual de los comprobantes.
  Router: `formato=xlsx|pdf` exige además `reportes.exportar` (403 sin él) y responde con `Content-Disposition: attachment; filename="zuquis-<tipo>-<desde>-<hasta>.xlsx"`.
  Precarga (migración de datos 0011): para cada sede, `UPDATE categorias_gasto SET cuenta_puc=… WHERE cuenta_puc IS NULL AND nombre=…`, según la tabla "Gastos" de `docs/puc-propuesta.md`. Lo mismo para los métodos: Efectivo → 1105, y los demás con titular negocio → 1110 y con titular dueño → 1325. `downgrade` no deshace nada (es una migración de datos; dejar un comentario).
  Reporte PUC (listado por cuenta, spec §4.4): sección "Movimientos" con columnas fecha, concepto, referencia, cuenta, monto. Conceptos y cuentas: venta 4120 (`total + descuento_total` de las no cortesía, es decir, el bruto), descuento 4175, costo de ventas 6120, cortesía 5295 (costo), merma 5295, ingreso por cancelación 4295, gasto con la `cuenta_puc` de su categoría, propina 2380, domicilio 2380, abono recibido 2805, dinero recibido con la `cuenta_puc` del método. Si falta el código → `"Sin código"`. Sección "Por cuenta" con el subtotal por cuenta. `ACCESO["puc"] = {reportes.ver}`.

- [ ] **Step 1: Pruebas que fallan:**
  - `test_suma_del_excel_igual_al_json`: generar el xlsx de `ventas`, abrirlo con `openpyxl.load_workbook(data_only=False)` y sumar en Python las celdas de pesos de "Por método de pago". El resultado es igual a `totales` del JSON, y la celda de total contiene `=SUM(`.
  - `test_excel_sin_permiso_exportar_403`: el contador sí puede y un usuario sin `reportes.exportar` → 403.
  - `test_pdf_responde_pdf`: `content-type application/pdf` y los bytes empiezan con `%PDF` (saltar con `pytest.skip` si `pdf_disponible()` es False, igual que en `test_comprobante.py`).
  - `test_precarga_puc`: después de las migraciones, la categoría "Arriendo del local" tiene 5120 y Efectivo tiene 1105.
  - `test_reporte_puc_por_cuenta`: una venta de 10.000 en efectivo con costo 4.000 y propina 1.000 → por cuenta: 4120=10.000, 6120=4.000, 2380=1.000, 1105=11.000.
  - `test_puc_sin_codigo_visible`.
- [ ] **Step 2:** FAIL. **Step 3:** `pip install openpyxl` en el entorno y en el Dockerfile si hace falta. Implementar. **Step 4:** PASS, con `pytest` completo.
- [ ] **Step 5: Commit** `feat(reportes): exportación a Excel y PDF, precarga y reporte PUC (#47)`.

---

### Task 8: Frontend — ECharts, tema de marca y cliente de reportes

**Files:**
- Modify: `frontend/package.json` (`echarts@^5`)
- Create: `frontend/src/components/graficos/Grafico.tsx`, `frontend/src/components/graficos/tema.ts`, `frontend/src/components/graficos/tema.test.ts`
- Create: `frontend/src/lib/reportes.ts`, `frontend/src/lib/reportes.test.ts`

**Interfaces:**
- Produces:
  ```ts
  // Grafico.tsx — wrapper propio sobre echarts/core (sin echarts-for-react)
  export default function Grafico(props: { opcion: EChartsCoreOption; alto?: number; etiqueta: string }): JSX.Element
  // registra: BarChart, LineChart, HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent, LegendComponent, SVGRenderer
  // init con renderer 'svg', ResizeObserver para redimensionar, dispose al desmontar, role="img" aria-label={etiqueta}
  // tema.ts
  export const COLORES: { fucsia: string; rosaBarra: string; dorado: string; cafeSuave: string; linea: string; pista: string; peligro: string }
  export function ejePesos(): object          // formatter con pesos(); miles como "64 mil" en etiquetas de barra
  export function enMiles(valor: number): string   // 64000 -> "64 mil", 1250000 -> "1,3 M"
  export function resaltarMaximo(valores: number[]): string[]   // color por barra: fucsia en el máximo, rosaBarra en el resto
  // reportes.ts
  export type TipoReporte = 'ventas'|'gastos'|'flujo-caja'|'utilidad-productos'|'inventario-valorizado'|'mermas'|'propinas'|'domicilios'|'descuentos-cortesias'|'ingresos-cancelacion'|'cierres'|'puc'
  export interface Rango { desde: string; hasta: string; sedeId?: string }
  export function atajo(nombre: 'hoy'|'ayer'|'semana'|'mes', hoy: Date): Rango   // semana = lunes..hoy, mes = día 1..hoy, en Bogotá
  export function useReporte(tipo: TipoReporte, r: Rango): UseQueryResult<Reporte>
  export function useGrupoGraficos(grupo: Grupo, r: Rango, activo: boolean): UseQueryResult<any-typed per grupo>
  export function useDashboard(): UseQueryResult<Dashboard>
  export async function exportar(tipo: TipoReporte, r: Rango, formato: 'xlsx'|'pdf'): Promise<void>  // apiBlob + descarga con el nombre del header
  ```
  Los colores de `COLORES` se leen de las variables CSS de `styles.css`, con los hex del archivo como respaldo para jsdom. Los tipos TS reflejan los esquemas de las Tareas 2–7, y los decimales son `string`.

- [ ] **Step 1: Pruebas que fallan:** `tema.test.ts`: `enMiles(64000) === '64 mil'`, `enMiles(1250000) === '1,3 M'`, y `resaltarMaximo([1,5,3])` da `[rosa, fucsia, rosa]`. `reportes.test.ts`: `atajo('semana', new Date('2026-11-12T12:00:00-05:00'))` → `{desde:'2026-11-09', hasta:'2026-11-12'}`, `atajo('ayer', …)` y `atajo('mes', …)` → `'2026-11-01'`.
- [ ] **Step 2:** `npm test -- --run` → FAIL.
- [ ] **Step 3:** `npm i echarts` e implementar.
- [ ] **Step 4:** `npm test -- --run && npm run lint` → PASS.
- [ ] **Step 5: Commit** `feat(reportes): componente de gráficos con ECharts y tema de marca`.

---

### Task 9: Pantalla de Inicio (dashboard)

**Files:**
- Modify: `frontend/src/pages/Inicio.tsx`
- Create: `frontend/src/pages/inicio/Dashboard.tsx`, `frontend/src/pages/inicio/Dashboard.test.tsx`
- Modify: `frontend/src/layout/navegacion.ts` (quitar `fase: 4` de Inicio)

**Interfaces:**
- Consumes: `useDashboard`, `Grafico` (con `React.lazy`), `COLORES`, `resaltarMaximo`, `enMiles`.

Recrea `docs/mockups/dashboard.png` tal cual: contexto "Viernes 16 de octubre · <sede>", el saludo con `saludo()`, `Chip` arena "Datos de ejemplo" si `datos_ejemplo`, y `Boton` "Nueva venta" → `/vender`. Cuatro tarjetas: "Ventas del día" (con "N ventas · sin contar propinas ni domicilios"), "Gastos del día" ("N gastos registrados"), "Ganancia estimada" ("Ventas menos costo real de insumos y gastos") y "Ticket promedio" ("Por venta"). "Ventas por hora" es un gráfico de barras ECharts con etiquetas `enMiles`, el máximo en fucsia y el eje en "3 p. m.". "Cómo pagaron hoy" son barras horizontales con "$280.600 · 41%" (se pueden hacer en HTML como en el mockup; son barras de progreso, no un gráfico). "Más vendidos hoy" muestra el top 5 con número en círculo y "N und". "Encargos para hoy" lleva el enlace "Ver todos" → `/encargos`. "Alertas de inventario" lleva "Ir a inventario" → `/inventario`, con fondo rosa para peligro y amarillo para advertencia. Se mantiene la redirección actual para quien no tiene `reportes.ver`. En celular, las tarjetas van en 2 columnas y los paneles apilados.

- [ ] **Step 1: Prueba que falla** `Dashboard.test.tsx` (con el `api` mockeado como en otras pruebas): renderiza "$684.500" y "38 ventas · sin contar propinas ni domicilios", muestra "Datos de ejemplo" solo si `datos_ejemplo`, y el enlace "Ir a inventario" apunta a `/inventario`.
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** `npm test -- --run && npm run lint && npm run build` → PASS.
- [ ] **Step 5:** Verificar en `dist/` que el chunk de entrada no contiene `echarts`: `grep -l "echarts" dist/assets/index-*.js` no debe devolver nada.
- [ ] **Step 6: Commit** `feat(inicio): dashboard con cifras del día (#45)`.

---

### Task 10: Reportes — encabezado, filtros y pestaña Gráficos

**Files:**
- Create: `frontend/src/pages/reportes/Reportes.tsx`, `FiltroRango.tsx`, `Graficos.tsx`, `graficos/` (un archivo por grupo: `Ganancia.tsx`, `Ventas.tsx`, `Productos.tsx`, `Gastos.tsx`, `Encargos.tsx`, `Cajeros.tsx`), `Reportes.test.tsx`
- Modify: `frontend/src/rutas.tsx` (`/reportes` con `React.lazy`), `frontend/src/layout/navegacion.ts` (quitar `fase`)

**Interfaces:**
- Consumes: `atajo`, `useGrupoGraficos`, `Grafico`, `COLORES`.
- Produces: `Reportes` lee y escribe `?vista=graficos|tablas&desde=&hasta=&sede=` en la URL (para compartir y recargar). Por defecto: Gráficos y semana.

Encabezado: contexto "Del 9 al 15 de noviembre · <sede>" y el título "Reportes". Píldoras Gráficos/Tablas, atajos Hoy · Ayer · Semana · Mes · Rango (dos `input type=date`), y selector de sede solo si el usuario tiene más de una sede. La pestaña Gráficos solo se muestra con `reportes.ver` o `reportes.ver_inventario`. Seis grupos con título en versalitas ("¿Estamos ganando?", "¿Cuándo y qué se vende?", "Productos", "Gastos, mermas y proveedores", "Encargos y clientes", "Por cajero"), en una grilla de 3 / 2 / 1 columnas según el ancho. Cada grupo usa `IntersectionObserver` para pedir sus datos (`activo`). Gráficos según spec §4.2: cascada con barras apiladas y base transparente; costo % con barras y línea; flujo con barras agrupadas; día a día con barras y una línea punteada del periodo anterior; calor con `heatmap` y `visualMap` de rosa claro a fucsia, días Lun–Dom y horas en "3 p. m."; categorías y mermas con barras horizontales; producido contra vendido con barras agrupadas (dorado/fucsia); gastos por mes con barras apiladas; por pagar como dos bloques de barras; 7, 13 y 14 como tablas cortas. Estado vacío por tarjeta: "Sin datos en este rango" en `cafe-suave`. Cada tarjeta lleva un `etiqueta` accesible.

- [ ] **Step 1: Prueba que falla** `Reportes.test.tsx`: con permisos de contador muestra las dos pestañas y los seis títulos de grupo. Con solo `reportes.ver_caja_propia` no muestra "Gráficos". Al hacer clic en "Mes", la URL cambia a `desde=…-01`.
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** `npm test -- --run && npm run lint && npm run build` → PASS.
- [ ] **Step 5: Commit** `feat(reportes): pantalla de reportes con galería de gráficos (#48)`.

---

### Task 11: Reportes — pestaña Tablas y exportación

**Files:**
- Create: `frontend/src/pages/reportes/Tablas.tsx`, `frontend/src/pages/reportes/TablaReporte.tsx`, `TablaReporte.test.tsx`
- Create: `frontend/e2e/reportes.spec.ts`

**Interfaces:**
- Consumes: `useReporte`, `exportar`, `Reporte`/`Seccion`/`Columna`.
- Produces: `TablaReporte({ seccion }: { seccion: Seccion })`, que formatea cada celda según `columna.tipo` (`pesos` → `pesos()` alineado a la derecha y en rojo con `−` si es negativo; `porcentaje` → "41,2 %"; `fecha` → `dd/mm/aaaa`; `cantidad` → `Decimal` con coma) y pone los totales al pie en negrita. En pantallas menores de 640 px cada fila pasa a ser una tarjeta con pares título/valor.

Selector de reporte con solo los tipos que permite el rol (el mismo mapa `ACCESO` que el backend, copiado en `reportes.ts` como `TIPOS_VISIBLES(permisos)`; el backend sigue mandando). Botones "Exportar a Excel" y "Exportar a PDF", solo con `reportes.exportar`.

- [ ] **Step 1: Prueba que falla** `TablaReporte.test.tsx`: una columna de pesos con `-12000` se muestra como "−$12.000" con la clase de peligro. Un porcentaje `"41.2"` se muestra "41,2 %". El total aparece al pie.
- [ ] **Step 2:** FAIL. **Step 3:** implementar. **Step 4:** `npm test -- --run && npm run lint && npm run build` → PASS.
- [ ] **Step 5: E2E** `reportes.spec.ts`, en escritorio y en el proyecto celular que ya usa Playwright: entrar como admin, ir a Reportes, elegir "Semana", ver el título "¿Estamos ganando?", pasar a Tablas, elegir "Ventas" y hacer clic en "Exportar a Excel" → `page.waitForEvent('download')` con un nombre que termina en `.xlsx`. Correr `npm run e2e -- reportes` → PASS (con el backend levantado igual que para los e2e existentes).
- [ ] **Step 6: Commit** `feat(reportes): pestaña de tablas con exportación a Excel y PDF (#48)`.

---

### Task 12: Caso de control de la semana y semilla de demostración

**Files:**
- Create: `backend/app/demo/__init__.py`, `backend/app/demo/semana.py`
- Modify: `backend/app/cli.py` (comando `semilla-demo`)
- Create: `backend/tests/control/fase4.md`, `backend/tests/test_control_fase4.py`

**Interfaces:**
- Consumes: los servicios de cada módulo (no la API), `fijar_ahora`, y todos los reportes, el dashboard y los grupos de gráficos.
- Produces: `def generar_semana(db, ctx, lunes: date) -> dict[str, Any]`, que crea la semana y devuelve los ids útiles. CLI: `python -m app.cli semilla-demo --lunes 2026-11-09`, que llama a `generar_semana`, activa la configuración `datos_ejemplo=True` de la sede y hace commit. Se niega si la sede ya tiene ventas (mensaje: "La sede ya tiene ventas; la semilla de ejemplo es solo para una base vacía").

Escenario mínimo (lunes a domingo, con `fijar_ahora` por cada hecho): dos compras del mismo insumo a precios distintos (una de contado y otra a crédito con fecha límite), una tercera compra a crédito sin fecha, producciones de dos productos, ventas cada día en al menos 3 horas distintas con pago mixto, una propina, un descuento autorizado, una cortesía, una venta anulada, un encargo con dos abonos entregado con saldo, otro cancelado con retención, domicilios de dos domiciliarios liquidados al cierre, gastos de caja y del banco (uno anulado), dos mermas con motivos distintos, un cierre diario y una diferencia de −2.000 en un día. `fase4.md` documenta cada hecho y calcula a mano, en tablas: los totales de la semana, la cascada, el costo % por semana, el flujo por titular, la utilidad de 2 productos, el inventario valorizado al domingo, las mermas, el por pagar, el top de clientes, los datos por cajero, el reporte PUC por cuenta y el dashboard del miércoles.

- [ ] **Step 1:** Escribir `fase4.md` con el escenario y los resultados calculados a mano.
- [ ] **Step 2: Prueba que falla** `test_semana_cuadra_al_peso`: llama a `generar_semana` y compara al peso cada cifra de `fase4.md` contra `GET /reportes/{tipo}`, `GET /reportes/graficos` (los 6 grupos), `GET /reportes/dashboard` con `reloj` el miércoles, y la suma del Excel de ventas.
- [ ] **Step 3:** `pytest tests/test_control_fase4.py -v` → FAIL (falta `generar_semana`).
- [ ] **Step 4:** Implementar `generar_semana` y el comando de la CLI.
- [ ] **Step 5:** `pytest tests/test_control_fase4.py -v` → PASS. Si una cifra no cuadra, **se corrige el código o el cálculo a mano después de entender la diferencia**, nunca se ajusta el esperado para que pase. Luego `pytest` completo → PASS.
- [ ] **Step 6: Commit** `test: caso de control de la Fase 4, una semana que cuadra al peso (#49)`.
