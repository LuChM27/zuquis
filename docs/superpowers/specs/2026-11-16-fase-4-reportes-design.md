# Fase 4 — Reportes, dashboard y galería de gráficos

Diseño acordado el 16/11/2026. Cubre los issues #45 (dashboard), #46 (reportes por rango), #47 (exportación y PUC), #48 (pantalla de reportes) y #49 (caso de control), más dos agregados de esta conversación: una **galería de 14 gráficos** y la **fecha límite de pago opcional en compras**.

## 1. Intención

El sistema ya registra todo el dinero (`caja_movimientos`) y todo el inventario (`movimientos_inventario`). Hoy solo se ve el día en Ventas y en Caja. La fase 4 deja que los dueños **vean el negocio en un rango de fechas**: si están ganando, cuándo y qué se vende, dónde se va la plata. Además le entrega al contador los movimientos con su código PUC.

Criterio de salida (PLAN §4): los reportes de una semana de datos de prueba coinciden al peso con los cálculos de control.

### Objetivos
- Dashboard de Inicio igual al mockup `docs/mockups/dashboard.png`.
- Reportes por rango en tablas, exportables a Excel y PDF, más el reporte PUC.
- Galería de 14 gráficos dentro de Reportes.
- Caso de control de una semana que cuadra al peso, gráficos incluidos.

### No objetivos
- Reportes de varias sedes a la vez. Se filtra por una sede, la del usuario o la que elija el admin.
- Gráficos que el usuario arme a su gusto, o reportes programados por correo.
- Que el contador cierre #1. Se precargan los códigos de la propuesta y se editan después.

### Anti-objetivos (aunque funcione, sería un fracaso)
- **Un gráfico que diga una cifra distinta a su tabla o a su Excel.**
- Que Vender se vuelva más lento por cargar la librería de gráficos.
- Cualquier cálculo de dinero con float, en el backend o en el frontend.
- Reportes que cargan todo el periodo en memoria. Se agrega en SQL.

## 2. Decisiones del usuario

- **El cajero no ve el dashboard.** Sigue entrando directo a Vender, como hoy. Lo de su turno ya está en Caja y Ventas.
- **La galería es una pestaña "Gráficos" dentro de Reportes (opción A).** La otra pestaña es "Tablas". El rango de fechas y la sede de arriba sirven para las dos.
- **Los 14 gráficos, en seis grupos:**

| Grupo | Gráfico |
|---|---|
| ¿Estamos ganando? | 1 Cascada de utilidad · 2 Costo de insumos % · 3 Flujo de caja |
| ¿Cuándo y qué se vende? | 4 Ventas día a día · 5 Día de la semana × hora · 6 Ventas por categoría |
| Productos | 7 Más vendidos y los que menos se mueven · 8 Producido contra vendido |
| Gastos, mermas y proveedores | 9 Gastos por categoría · 10 Mermas · 11 Cuentas por pagar por vencimiento |
| Encargos y clientes | 12 Encargos · 13 Clientes que más encargan |
| Por cajero | 14 Ventas, descuentos y regalos, y diferencias en los cierres |

- **Librería de gráficos: Apache ECharts** (no CSS a mano), para poder hacer gráficos más complejos después.
- **Fecha límite de pago opcional en las compras a crédito.** Si una cuenta por pagar no la tiene, el gráfico 11 la clasifica por antigüedad.
- **Reporte PUC como listado por cuenta**, no como libro diario de partida doble (ver 4.4).

## 3. Enfoques considerados

**Ubicación de la galería.** A: pestaña dentro de Reportes (elegida). B: pantalla "Análisis" aparte, que suma un ítem más a un menú que ya tiene 9 y repite el filtro de fechas. C: un gráfico encima de cada tabla, sin la vista de conjunto que se buscaba.

**Gráficos.** CSS a mano: liviano, pero no escala a gráficos complejos (lo descartó el usuario). Recharts: componentes de React y unos 150 KB, pero no trae mapa de calor y la cascada sale con trucos. **ECharts (elegida):** trae de fábrica el mapa de calor, la cascada, las barras apiladas y de rango, el zoom y el detalle al tocar; pesa unos 350 KB con *tree-shaking* y se carga en diferido.

## 4. Diseño

### 4.1 Backend: módulo `reportes`

Nuevo módulo `backend/app/modules/reportes/` con `router.py · schemas.py · service.py` (no tiene tablas propias) y un archivo de consultas por tema si `service.py` crece: `ventas.py`, `dinero.py`, `inventario.py`, `graficos.py`, `exportar.py`.

**Regla central: una sola fuente por cifra.** Cada cifra sale de una función de consulta. La tabla JSON, el Excel, el PDF, los gráficos y el dashboard llaman a esas mismas funciones. Los gráficos no tienen consultas propias que repitan una cifra de una tabla. Si un gráfico necesita otra forma de los datos (por hora, por semana), la agrupación se hace en SQL dentro de la misma función, con un parámetro de agrupación.

**Definiciones de las cifras** (respetan RN-15, RN-17, RN-18, RN-20, RN-22 y la decisión de #1):

| Cifra | Definición |
|---|---|
| Ventas | `SUM(ventas.total)` con `estado='pagada'`. Ya excluye propina y valor del domicilio. Los encargos cuentan el día de la entrega, porque es cuando se crea su venta (RN-20). |
| Cortesía (cómo está guardada) | Una venta `pagada` con `subtotal > 0`, `total = 0` y `costo_total > 0` (ver `cortesia=` en `ventas/service.py`). No crea fila en `gastos`. |
| Costo de insumos (costo real) | `SUM(ventas.costo_total)` de las ventas pagadas **que no son cortesía** (PEPS). Es lo que va a 6120. |
| Costo de cortesías | `SUM(ventas.costo_total)` de las cortesías. Es un gasto de cortesía (RN-17, cuenta 5295), **no** costo de ventas. Su valor bruto cuenta como descuento del 100 % en "descuentos y cortesías". |
| Gastos | `gastos` con `estado` vigente, por `gastos.fecha`, de todas las fuentes. |
| Mermas | `SUM(mermas.costo_total)`. Gasto aparte, no costo de ventas (#1). |
| Ingresos por cancelación | `SUM(encargos.monto_retenido)` de los cancelados con `cancelado_en` en el rango (RN-22), igual que el `resumen` actual. |
| Utilidad (cascada) | Ventas − costo de insumos − regalado (costo de cortesías) − gastos − mermas, con los ingresos por cancelación como barra positiva aparte. Propinas y domicilios no entran: son dinero de terceros. |
| Costo de insumos % | Costo de insumos (sin cortesías) ÷ ventas, por semana ISO. Se calcula en `Decimal` y viaja como string. |
| Flujo de caja | Todo el dinero que entra y sale: `caja_movimientos` por tipo y por día, **más** los gastos con fuente banco o dueños y los `pagos_compra` sin `caja_sesion_id`, marcados "fuera de caja". Lo que ya generó un `caja_movimiento` no se suma otra vez. Los abonos cuentan el día en que entran. Subtotal por `metodos_pago.titular` (negocio / dueño). |

**Fechas.** Los rangos usan la fecha local `America/Bogota` del hecho (`ventas.fecha`, `gastos.fecha`, etc.), igual que el `resumen` actual de ventas. El dashboard es la excepción: muestra **la caja abierta de la sede** si la hay, y si no, el día calendario de hoy. *(Decisión del diseñador: es lo que hace hoy el resumen de ventas. Los cierres se reportan por la fecha de cierre.)*

**Endpoints** (todos con `sede_id` del contexto. El admin puede pasar `sede_id` en el filtro):

- `GET /reportes/dashboard` → KPIs, ventas por hora, por método, top 5, encargos de hoy con saldo, alertas (reusa `inventario.alertas`), `datos_ejemplo: bool`.
- `GET /reportes/{tipo}?desde=&hasta=&formato=json|xlsx|pdf`, con `tipo` ∈ `ventas`, `gastos`, `flujo-caja`, `utilidad-productos`, `inventario-valorizado` (usa solo `hasta` como fecha de corte), `mermas`, `propinas`, `domicilios`, `descuentos-cortesias`, `ingresos-cancelacion`, `cierres`, `puc`.
- `GET /reportes/graficos?desde=&hasta=&grupo=` → los datos de los 14 gráficos, por grupo para no calcular los seis grupos de una vez. El cliente pide cada grupo cuando entra en pantalla.

**Permisos** (ya existen en `core/permisos.py`):
- `reportes.ver`: todo (admin, contador).
- `reportes.ver_inventario`: solo inventario valorizado, mermas y los gráficos 8 y 10 (producción).
- `reportes.ver_caja_propia`: en Tablas, solo `ventas` y `cierres` limitados a la caja abierta de su sede (todas las ventas de esa sesión, porque la caja es del turno y no de una persona). Nada de Gráficos (cajero). *(Decisión del diseñador.)* En la práctica el cajero casi no entra a Reportes, porque su pantalla es Vender.
- `reportes.exportar`: los formatos xlsx y pdf.
- La validación está siempre en el backend. El frontend solo oculta.

**Rendimiento.** Todo se agrega con `GROUP BY` en PostgreSQL. Se agregan los índices `(sede_id, fecha)` que falten en `ventas`, `gastos`, `caja_movimientos`, `mermas`, `movimientos_inventario` y `producciones`, en una migración de Alembic. Nada de traer filas al proceso para sumarlas en Python.

**Inventario valorizado a una fecha:** se reconstruye por lote desde `movimientos_inventario` hasta la fecha de corte (cantidad por lote × `costo_unitario` del lote), no desde `cantidad_disponible`. Así sirve para fechas pasadas.

### 4.2 Datos de cada gráfico

| # | Datos | Forma ECharts |
|---|---|---|
| 1 | ventas, costo insumos, regalado (cortesías), gastos, mermas, ingreso por cancelación, utilidad | cascada (barras apiladas con base invisible) |
| 2 | % por semana | barras + línea |
| 3 | entradas y salidas por día, desglose negocio/dueño | barras agrupadas |
| 4 | ventas por día del rango y del periodo anterior de igual largo | barras + línea punteada |
| 5 | ventas por día de la semana × hora local | `heatmap` |
| 6 | ventas por categoría de la carta (monto y %) | barras horizontales |
| 7 | top 10 y últimos 10 productos activos por unidades (incluye los de 0) | dos listas cortas |
| 8 | por producto de vitrina: producido (`producciones`) vs vendido (salidas por venta) en el rango | barras agrupadas |
| 9 | gastos por categoría y por mes | barras apiladas |
| 10 | mermas por motivo y por ítem, en pesos | barras horizontales |
| 11 | saldo por pagar: vencidas / esta semana / próximas (con fecha) + 0–15 / 16–30 / >30 días (sin fecha) | barras horizontales en dos bloques |
| 12 | encargos entregados vs cancelados por semana; total de abonos vigentes de encargos que **a la fecha `hasta`** no estaban entregados ni cancelados (se usa `entregado_en` / `cancelado_en`) | barras + cifra |
| 13 | top 10 clientes por número de encargos y total | tabla corta |
| 14 | por cajero (`ventas.usuario_id`): vendido, descuentos y cortesías (con quién autorizó); diferencias de arqueo asignadas a **quien cerró la caja** (`cerrada_por`), que es quien contó | tabla corta |

Los gráficos 7, 13 y 14 se muestran como tablas cortas, porque comparar nombres se lee mejor así.

### 4.3 Compras: fecha límite de pago opcional

- Migración: `compras.fecha_limite_pago DATE NULL`.
- `CompraCrear` acepta `fecha_limite_pago` opcional, que solo tiene sentido si la compra queda por pagar. Si viene en una compra de contado se ignora o se rechaza con un error claro *(se rechaza: decisión del diseñador)*.
- `NuevaCompra.tsx`: el campo "Pagar antes del" aparece solo cuando se elige "queda por pagar". No es obligatorio.
- `PorPagar.tsx` muestra la fecha y marca en rojo las vencidas.
- *Decisión del diseñador:* no hay plazo por defecto por proveedor. Se puede agregar después sin romper nada.

### 4.4 Exportación y PUC (#47)

- `openpyxl` (nueva dependencia): montos como números enteros con formato `$ #,##0` en el locale de la hoja, y cantidades como `Decimal` exacto. Encabezado con negocio, sede, rango y fecha de generación. Fila de totales con fórmulas `SUM`, cuyo resultado coincide con el JSON (lo verifica una prueba).
- PDF con WeasyPrint, reusando `shared/pdf.py` (logo, `pesos`, línea visual).
- Precarga de PUC: una migración de datos que llena `cuenta_puc` en las categorías de gasto y los métodos de pago **solo donde está vacía**, con los códigos de `docs/puc-propuesta.md`. Si después el contador cambia algo, se edita en Configuración.
- **Reporte PUC: listado por cuenta (decidido por el usuario; no es un libro diario de partida doble).** Una fila por hecho del rango con fecha, concepto, referencia (n.º de venta, gasto, etc.), cuenta y monto, según la tabla de la propuesta: ventas 4120, costo de ventas 6120, descuentos 4175, cortesías 5295, mermas 5295, cancelación 4295, gastos según su categoría, propinas y domicilios 2380, abonos de encargos sin entregar 2805, y el dinero recibido según la `cuenta_puc` de su método (1105, 1110 o 1325). Al final, un subtotal por cuenta. Si una categoría o método no tiene código, aparece como "Sin código" y eso salta a la vista. No incluye compras ni pagos a proveedores, porque la propuesta no tiene esas cuentas. Queda anotado en #1 como pregunta para el contador si más adelante quiere un libro diario completo.

### 4.5 Frontend

- **Dependencias:** `echarts` y `echarts-for-react` (o un *wrapper* propio de unas 40 líneas con `echarts/core`. El que construye decide; se prefiere el propio si evita problemas con React 19). Se registran solo los módulos usados: Bar, Line, Heatmap, Grid, Tooltip, VisualMap, Legend y el renderer SVG.
- **Carga diferida:** `Inicio` y `Reportes` cargan los gráficos con `React.lazy`. Vender no importa nada de ECharts. Hay que verificar en el *build* que el chunk de echarts no esté en el de entrada.
- **Tema:** un objeto de tema ECharts construido desde los tokens de `styles.css` (fucsia `#C42D72`, rosa, dorado, crema; Montserrat en los ejes; montos con `pesos()` de `lib/formato`). La hora pico va en fucsia y el resto en rosa claro, como en el mockup.
- **Inicio:** recrea el mockup tal cual: saludo, fecha y sede, chip "Datos de ejemplo", botón "Nueva venta", 4 KPIs, ventas por hora, cómo pagaron hoy, más vendidos, encargos para hoy ("Ver todos" lleva a Encargos), alertas ("Ir a inventario"). Quien no tiene `reportes.ver` sigue siendo redirigido, como hoy.
- **Reportes** (`/reportes`): encabezado con contexto (rango · sede) y título serif. Pestañas Gráficos / Tablas. Atajos Hoy · Ayer · Semana · Mes · Rango, y selector de sede para el admin. En **Gráficos**, los seis grupos con su título (como en el boceto aprobado), en grilla de 3 columnas en escritorio y 1 en celular; cada grupo pide sus datos cuando aparece en pantalla. En **Tablas**, un selector de reporte, la tabla con totales al pie y los botones "Exportar a Excel" y "Exportar a PDF" (solo con `reportes.exportar`). En celular, las tablas anchas pasan a tarjetas apiladas.
- Sin mockup propio: sigue el sistema visual de `docs/mockups/README.md`.

### 4.6 "Datos de ejemplo"

El script de semillas de #49, cuando se corre en modo demostración, pone en la configuración **de la sede** (la configuración ya se guarda por `sede_id`) la marca `datos_ejemplo = true`. El dashboard muestra el chip si la marca está activa. La marca se apaga desde Configuración, o sola al cargar los datos reales en la fase 5. *(Decisión del diseñador.)*

### 4.7 Caso de control (#49)

- `backend/tests/control/semana_fase4.py`: una semana realista armada con los servicios reales (compras a precios distintos, producción, ventas con pago mixto, propinas y descuentos, una cortesía, encargos con abonos, entrega y una cancelación con retención, domicilios, gastos de varias fuentes, mermas, una compra a crédito con fecha límite y otra sin ella, cierres con una diferencia).
- Los valores esperados se escriben a mano en el archivo, calculados por fuera (como en `test_control_fase2.py` y `test_control_fase3.py`), **no** con las funciones que se están probando.
- `test_control_fase4.py` compara al peso cada reporte JSON, el dashboard de un día, los datos de los 14 gráficos y la suma del Excel.
- El mismo generador sirve como semilla de demostración (`cli`) que pone la marca de 4.6.

### 4.8 Pruebas
- pytest de cada función de consulta, con permisos por rol (cajero, producción, contador, admin).
- Guardia: ninguna respuesta de reportes con float (los decimales viajan como string).
- Vitest: el tema y los formateadores de ejes; Reportes renderiza las pestañas y oculta exportar sin el permiso.
- Playwright: abrir Reportes, cambiar a "Semana", ver la galería y descargar un Excel, en escritorio y celular.

## 5. Orden de trabajo

Rama `fase-4` desde `main`. Orden: compras con fecha límite (es chico y desbloquea el gráfico 11) → #46 consultas y reportes JSON → #45 dashboard (backend y pantalla) → galería (endpoint de gráficos y pestaña) → #47 Excel, PDF y PUC → #48 pestaña Tablas → #49 caso de control y semillas. Un commit por entregable con su número de issue.

## 6. Lo que queda al criterio de quien construye
- Si `service.py` se divide por tema, y los nombres internos.
- El *wrapper* de ECharts propio o la librería `echarts-for-react`.
- Los textos de los ejes y de los detalles al tocar, en el tono de la interfaz (español, `$12.500`, `dd/mm/aaaa`).
- Cómo se ve el estado vacío de cada gráfico cuando el rango no tiene datos, siguiendo el sistema visual.
