# Zuqui's — Plan general de desarrollo

Plan de trabajo derivado de la [especificación](especificacion.md) (16/10/2026). La especificación es la fuente de verdad; este documento ordena el trabajo, fija los entregables de cada fase y deja anotadas las decisiones abiertas. Cada entregable tiene un issue en GitHub, agrupado en un milestone por fase.

## 1. Resumen

Sistema web propio para Zuqui's Repostería: punto de venta, caja con arqueo, inventario de insumos y productos con costo real por lote (PEPS), recetas y costeo, compras, producción, mermas, encargos con abonos, domicilios, gastos y reportes.

- **El inventario es el motivo principal del proyecto**, por eso se construye antes que el POS.
- Corre primero en un PC del local (Docker Compose) y luego en un servidor con HTTPS, sin cambiar código.
- Responsive y PWA: se diseña primero para celular.
- Preparado desde el inicio para varias sedes (`sede_id`), trabajo sin conexión (`Idempotency-Key`) y facturación electrónica (impuestos configurables, desactivados).

## 2. Stack

| Capa | Tecnología |
|---|---|
| Frontend | React + Vite + TypeScript, React Router, TanStack Query, Tailwind CSS, vite-plugin-pwa, decimal.js |
| Backend | Python 3.12+, FastAPI, Pydantic v2, Uvicorn |
| Datos | PostgreSQL 16+, SQLAlchemy 2, Alembic |
| Seguridad | PyJWT, argon2-cffi |
| Reportes | openpyxl, WeasyPrint |
| Pruebas | pytest, httpx, Vitest, Playwright |
| Infraestructura | Docker Compose, Caddy, GitHub Actions |

## 3. Principios que todos los issues respetan

1. **Nada de float para dinero ni cantidades** (RNF-01, sección 6). Pesos en `BIGINT`/`int`; costos `NUMERIC(18,6)`, cantidades `NUMERIC(18,4)`, porcentajes `NUMERIC(7,4)` como `Decimal`; decimales viajan como string en JSON. Redondeo a peso una sola vez con `ROUND_HALF_UP`. Una prueba automática falla si aparece una columna `Float`.
2. **Dos libros de solo inserción**: `caja_movimientos` (dinero) y `movimientos_inventario` (existencias). Nada se borra; se anula o se compensa (RNF-09, RN-01).
3. **Una transacción por operación** que mueva dinero o inventario. Si algo falla, no se guarda nada.
4. **Capas**: routers validan y autorizan; servicios tienen las reglas (PEPS, caja, encargos); repositorios acceden a datos. Cada módulo: `router.py · schemas.py · service.py · models.py`.
5. **Permisos en el backend siempre**. Ocultar botones en el frontend no reemplaza la validación.
6. **Fechas en UTC**, mostradas en `America/Bogota`. El día contable lo define la caja, no la medianoche.
7. **Español en la interfaz**, `$12.500`, `dd/mm/aaaa`, números tabulares alineados a la derecha.

## 4. Fases y entregables

Las duraciones se fijan cuando se confirmen disponibilidad y fecha de entrega (pendiente, sección 14 de la especificación).

### Fase 0 — Base
Repositorio, Docker Compose, PostgreSQL, Alembic, módulo de dinero, errores uniformes, autenticación, usuarios, roles configurables, sedes, configuración, auditoría, idempotencia, archivos, esqueleto del frontend con la línea visual, CI.

**Sale cuando:** el login funciona con permisos y las pruebas corren en cada cambio.

### Fase 1 — Inventario
Carta (categorías, productos, adiciones, historial de precios), unidades, insumos y presentaciones, motor de lotes y PEPS, proveedores y compras con lotes y cuentas por pagar, recetas versionadas y costeo, producción, mermas, ajustes, kardex, alertas y verificación nocturna. Pantallas de inventario, carta, recetas, compras y producción.

**Sale cuando:** una compra crea lotes; una producción los consume por PEPS y crea stock terminado con costo correcto (caso de control calculado a mano).

### Fase 2 — Venta y caja
Caja (apertura, movimientos manuales, cierre con arqueo, historial), ventas con pago mixto, propinas, descuentos y cortesías con tope y autorización, anulaciones, comprobante PDF, gastos, PIN de cajero. Pantallas de POS (escritorio y celular), caja y gastos.

**Sale cuando:** un día completo de ventas cuadra en caja e inventario contra un caso de prueba calculado a mano.

### Fase 3 — Encargos y domicilios
Clientes, encargos con estados, abonos, entrega (crea la venta), cancelación con decisión del admin, domicilios con liquidación al domiciliario en el cierre de caja.

**Sale cuando:** un encargo con dos abonos, entrega y una cancelación con devolución parcial quedan reflejados en caja y reportes.

### Fase 4 — Reportes
Dashboard, reportes por rango, utilidad por producto, inventario valorizado, exportación a Excel y PDF, reporte de movimientos con PUC para el contador.

**Sale cuando:** los reportes de una semana de datos de prueba coinciden con los cálculos de control.

### Fase 5 — Producción y salida a servidor
Instalación en el PC del local, respaldos automáticos, carga de carta e inventario inicial, capacitación, semana piloto; luego servidor con HTTPS y PWA en celular.

**Sale cuando:** el negocio opera una semana completa solo con el sistema.

### Fase 6 — Evolución
POS sin conexión, segunda sede, facturación electrónica, impresora térmica, cajón monedero y lector de códigos. Se planifica según la operación real.

## 5. Dependencias entre bloques

```text
Fase 0  dinero ─┬─ modelo base ─ auth ─ roles/permisos ─ configuración ─ auditoría
                └─ frontend base (tema, layout, cliente HTTP)
Fase 1  carta ─┐
        insumos ─ motor PEPS ─┬─ compras
                              ├─ recetas ─ producción
                              └─ mermas/ajustes ─ kardex/alertas
Fase 2  caja ─ ventas (usa motor PEPS + recetas) ─ descuentos ─ anulaciones ─ cierre
Fase 3  clientes ─ encargos/abonos (usa caja + ventas) ─ domicilios (se integran al cierre)
Fase 4  reportes (leen los dos libros)
Fase 5  despliegue, respaldos, carga inicial, piloto
```

## 6. Estrategia de pruebas

- **Unitarias (pytest)**, obligatorias antes de fusionar: PEPS con varios lotes, conversión de unidades, redondeo, costo de receta, arqueo.
- **Integración** contra PostgreSQL real en Docker, incluidas transacciones que deben revertirse completas.
- **Guardia de tipos**: falla si un modelo tiene columna `Float`.
- **Casos contables de control**, calculados a mano y versionados en `backend/tests/control/`: un día de ventas, una semana con compras a precios distintos, un encargo cancelado. Deben cuadrar al peso.
- **Frontend**: Vitest para componentes; Playwright para vender, cerrar caja y registrar compra, en escritorio y celular.
- **Aceptación con el negocio** al final de cada fase, con datos reales de la carta.

## 7. Forma de trabajo

- Rama principal `main` protegida; una rama por issue (`feat/<n>-descripcion`), PR con CI en verde.
- Milestones = fases. Etiquetas: `area:*` (backend, frontend, infra), `modulo:*`, `tipo:*`.
- Cada issue indica los RF/RN/RNF que cubre, para trazar requerimiento → código → prueba.
- Las decisiones abiertas tienen issue propio con etiqueta `tipo:decision` y deben cerrarse antes de la fase que las usa.

## 8. Decisiones abiertas y huecos detectados

### Con el contador (issue #1)
Abiertos:
- Régimen tributario, impuesto aplicable (IVA o impuesto al consumo) y proveedor de facturación electrónica. No bloquea hasta la fase 6: los impuestos quedan desactivados.
- Abono retenido en cancelación como ingreso (RN-22, propuesta). Se necesita en la fase 3.
- Costo de ajustes positivos = costo del último lote (RN-10, propuesta). Se necesita en la fase 1.
- Códigos PUC: validar la [propuesta](puc-propuesta.md) antes de la fase 4.

Resueltos el 17/10/2026: costeo PEPS por lote aprobado; cortesías como gasto por su costo (RN-17) aprobado.

### Huecos del modelo (issue #2, resueltos el 17/10/2026)
Ya incorporados a la especificación:
- **Domiciliarios**: tabla `domiciliarios` (nombre, teléfono, activo); no son usuarios del sistema.
- **Número de encargo**: `encargos.numero`, consecutivo por sede como las ventas.
- **Costo teórico** (RF-07): se calcula con el último costo de compra de cada insumo. El costo real sigue saliendo por PEPS.
- **Venta sin stock permitida** (RF-16): lo que falta queda como faltante por regularizar (`faltantes_inventario`) con costo estimado; el stock nunca queda negativo.
- **Fucsia**: `--fucsia #C42D72` (5,3:1 con blanco) para botones y texto; `#E2468F` solo como acento decorativo.
- Tablas técnicas: `idempotencia`, `sesiones_refresh`, `proveedor_insumos`, `consecutivos` y el campo `usuarios.pin_hash`.

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Errores de redondeo o de PEPS que descuadran caja e inventario | Módulo de dinero único, pruebas unitarias exhaustivas, casos de control a mano, verificación nocturna RN-09 |
| Pérdida de datos en el PC del local | Respaldo diario fuera del PC, restauración probada cada mes |
| Recetas incompletas al arrancar ⇒ costos falsos | Carga inicial guiada en fase 5; RF-16 configurable para no frenar la venta |
| Alcance grande para una sola persona | Fases con criterio de salida; fase 6 fuera del compromiso inicial |
| Decisiones contables abiertas | Issue #1, cerrar cada punto antes de la fase que lo usa (RN-10 en fase 1, RN-22 en fase 3, PUC en fase 4) |
