# Decoración en encargos — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cada ítem de un encargo puede llevar una decoración (referencia + valor) que suma al total y sale como línea propia en la venta, y desde el encargo se registran gastos de "Materiales de decoración" ligados a él.

**Architecture:** Dos columnas opcionales en `encargo_items`, una FK opcional `gastos.encargo_id` y una categoría de gasto sembrada; una sola migración `0008`. El endpoint nuevo `POST /encargos/{id}/gastos` reutiliza `gastos.service.crear`. El frontend extiende `FormEncargo`, `DetalleEncargo` y el detalle de Gastos.

**Tech Stack:** FastAPI + SQLAlchemy 2 + Alembic + pytest (backend); React + TanStack Query + Tailwind + Playwright (frontend).

**Spec:** `docs/superpowers/specs/2026-11-16-decoracion-encargos-design.md`

## Global Constraints

- Rama `fase-3`; todo entra al PR #61.
- Textos de la interfaz y mensajes de error en español, sin tecnicismos (estilo del resto del proyecto).
- Pesos enteros (`Pesos`, `MontoPesos`); nada de floats.
- Categoría: nombre exacto `"Materiales de decoración"`, cuenta PUC `"5195"`.
- La decoración vale por ítem, no por unidad; no toca inventario; solo existe en encargos (el POS no cambia).
- Verificación final: `ruff`, `mypy` (si está en CI), `pytest` (también con `PGTZ=UTC`), `eslint`, `vitest`, Playwright completo.

## Review Focus

1. Quitar la decoración al editar un encargo con abonos y que el total quede por debajo de lo abonado → debe responder `ABONO_EXCEDE_SALDO` (Task 1 lo prueba).
2. Referencia escrita sin valor, o valor sin referencia → 422 "La decoración necesita referencia y valor." en API y mensaje en el formulario (Tasks 1 y 4).
3. Cajero (solo `gastos.crear_caja`) registrando un gasto de decoración desde banco o dueños → 403, igual que en Gastos (Task 3).
4. Gasto de decoración anulado desde Gastos → deja de contar en `gasto_decoracion` del encargo (Task 3).
5. Referencia de 200 caracteres → la línea de venta "Decoración: …" se recorta a 200 y la entrega no falla (Task 2).

---

### Task 1: Decoración en los ítems (modelo, migración, API)

**Files:**
- Modify: `backend/app/modules/encargos/models.py` (EncargoItem)
- Modify: `backend/app/modules/gastos/models.py` (Gasto.encargo_id, CATEGORIAS_INICIALES)
- Create: `backend/migrations/versions/20261116_0008_fase_3_decoracion_encargos.py`
- Modify: `backend/app/modules/encargos/schemas.py` (ItemEntrada, ItemSalida)
- Modify: `backend/app/modules/encargos/service.py` (`_items`, `_total`, `salida`)
- Test: `backend/tests/test_decoracion_encargos.py` (nuevo)

**Interfaces:**
- Produces: `EncargoItem.decoracion: str | None`, `EncargoItem.decoracion_precio: int | None`; `Gasto.encargo_id: uuid.UUID | None`; `gastos.models.CATEGORIA_DECORACION = ("Materiales de decoración", "5195")`; JSON del ítem con `decoracion`, `decoracion_precio`.

- [ ] **Step 1: Tests que fallan** en `test_decoracion_encargos.py` (usar fixtures `cliente, admin, cliente_a, carta, metodos, caja_abierta` y helpers de `tests.fixtures_encargos`):
  - `test_decoracion_suma_al_total_una_vez_por_item`: ítem `{"producto_id": carta["pastel"]["id"], "cantidad": "2", "precio": 4000, "decoracion": "Letras doradas", "decoracion_precio": 15000}` → `total == 23000`; el ítem trae `decoracion == "Letras doradas"`, `decoracion_precio == 15000`, `subtotal == 8000`.
  - `test_decoracion_necesita_referencia_y_valor`: solo `decoracion` → 422; solo `decoracion_precio` → 422; `decoracion: "   "` con precio → 422; `decoracion_precio: 0` → 422.
  - `test_item_sin_decoracion_sigue_igual`: `torta(...)` → `decoracion is None`, `decoracion_precio is None`, total 90000.
  - `test_editar_quita_la_decoracion_y_respeta_lo_abonado`: crear con torta 90000 + decoración 20000 (total 110000), abonar 100000, PATCH items sin decoración → 422 `ABONO_EXCEDE_SALDO`; PATCH cambiando decoración a 30000 → total 120000.
  - `test_categoria_de_decoracion_sembrada`: `GET /categorias-gasto` incluye `{"nombre": "Materiales de decoración", "cuenta_puc": "5195"}`.
- [ ] **Step 2:** `cd backend && .venv/Scripts/python.exe -m pytest tests/test_decoracion_encargos.py -q` → FAIL.
- [ ] **Step 3: Modelo.** `EncargoItem`: `decoracion: Mapped[str | None] = mapped_column(String(200))`, `decoracion_precio: Mapped[int | None] = mapped_column(MontoPesos())`; checks `"(decoracion IS NULL) = (decoracion_precio IS NULL)"` (name `decoracion_completa`) y `"decoracion_precio IS NULL OR decoracion_precio > 0"` (name `decoracion_positiva`). `Gasto`: `encargo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("encargos.id"), index=True)`. Agregar `CATEGORIA_DECORACION` y meterla en `CATEGORIAS_INICIALES`.
- [ ] **Step 4: Migración 0008** (`down_revision = "0007"`): columnas y checks anteriores, `gastos.encargo_id` con FK e índice, e `INSERT` de la categoría para cada sede de `sedes` que no la tenga (llenar las columnas de `Operativo` como lo hagan las migraciones previas; `gen_random_uuid()` para id). `downgrade` revierte todo, borrando la categoría solo si no tiene gastos.
- [ ] **Step 5: Esquemas.** `ItemEntrada`: `decoracion: str | None = Field(default=None, max_length=200)`, `decoracion_precio: Pesos | None = Field(default=None, gt=0)`; en el validador, tras `strip`, si exactamente uno de los dos está presente → `ValueError("La decoración necesita referencia y valor.")`. `ItemSalida`: `decoracion: str | None`, `decoracion_precio: int | None`.
- [ ] **Step 6: Servicio.** `_items` copia `decoracion` (strip, vacío → None) y `decoracion_precio`; `_total` suma `i.decoracion_precio or 0` por ítem; `salida` llena los dos campos del ítem. La descripción automática del encargo no cambia.
- [ ] **Step 7:** `alembic upgrade head` contra la base de pruebas y correr el archivo → PASS; correr `tests/test_encargos.py` → PASS.
- [ ] **Step 8: Commit** `feat(encargos): decoración opcional por ítem con referencia y valor`.

### Task 2: La decoración sale como línea de la venta al entregar

**Files:**
- Modify: `backend/app/modules/ventas/service.py` (`crear_de_encargo`, ~línea 515)
- Test: `backend/tests/test_decoracion_encargos.py`

**Interfaces:**
- Consumes: `EncargoItem.decoracion`, `EncargoItem.decoracion_precio` (Task 1).

- [ ] **Step 1: Tests que fallan:**
  - `test_entregar_agrega_linea_de_decoracion_sin_inventario`: pastel ×10 a 4000 con decoración "Topper de foto" 12000 + ítem personalizado "Caja" 5000; alistar, entregar pagando 57000 en efectivo → `stock(db, "producto", pastel) == D("2")`; `venta["total"] == 57000`; `[(i["descripcion"], i["precio_unitario"], i["costo_total"]) for i in venta["items"]]` empieza con la línea del pastel, luego `("Decoración: Topper de foto", 12000, 0)`, luego `("Caja", 5000, 0)`. (Ajustar la clave de descripción a como la exponga `GET /ventas/{id}`.)
  - `test_referencia_larga_se_recorta_en_la_venta`: decoración de 200 "x" → entrega 200 OK y la descripción de la línea mide 200.
- [ ] **Step 2:** correr → FAIL.
- [ ] **Step 3:** en `crear_de_encargo`, al armar `lineas`, después de cada ítem con decoración agregar `_Linea(cantidad=Decimal(1), precio_unitario=i.decoracion_precio, producto=None, modificadores=[], precios_mods=[], bruto=i.decoracion_precio, descuento=0, descripcion=f"Decoración: {i.decoracion}"[:200])`.
- [ ] **Step 4:** correr el archivo, `tests/test_encargos.py` y `tests/test_control_fase3.py` → PASS.
- [ ] **Step 5: Commit** `feat(encargos): la decoración sale como línea propia en la venta`.

### Task 3: Gastos de decoración ligados al encargo

**Files:**
- Modify: `backend/app/modules/gastos/service.py` (`crear`, `salida`, nueva `categoria_decoracion`)
- Modify: `backend/app/modules/gastos/schemas.py` (GastoSalida)
- Modify: `backend/app/modules/encargos/schemas.py` (GastoDecoracionEntrada, GastoBreve, EncargoSalida)
- Modify: `backend/app/modules/encargos/service.py` (`registrar_gasto`, `salida`)
- Modify: `backend/app/modules/encargos/router.py`
- Test: `backend/tests/test_decoracion_encargos.py`

**Interfaces:**
- Produces:
  - `gastos.service.categoria_decoracion(db, ctx) -> CategoriaGasto`: busca por nombre en la sede; si no existe la crea (activa, PUC 5195).
  - `gastos.service.crear(db, ctx, datos: GastoCrear, encargo_id: uuid.UUID | None = None) -> Gasto`.
  - `GastoSalida.encargo_id: uuid.UUID | None`, `GastoSalida.encargo_numero: int | None = None`.
  - `encargos.schemas.GastoDecoracionEntrada`: `descripcion: str (3..200)`, `monto: Pesos (gt 0)`, `metodo_pago_id: uuid.UUID`, `fuente: Fuente`.
  - `encargos.schemas.GastoBreve`: `id, fecha: date, descripcion, monto: int, fuente, estado`.
  - `EncargoSalida` + `decoracion_cobrada: int`, `gasto_decoracion: int` (solo `registrado`), `gastos_decoracion: list[GastoBreve]` (todos, por fecha).
  - `encargos.service.registrar_gasto(db, ctx, encargo_id, datos: GastoDecoracionEntrada) -> Encargo`.
  - `POST /encargos/{encargo_id}/gastos` → 201 `EncargoSalida`; dependencia `requiere_alguno("gastos.crear", "gastos.crear_caja")`; con idempotencia (`_con_idempotencia`).
- [ ] **Step 1: Tests que fallan:**
  - `test_gasto_de_decoracion_queda_ligado_y_en_gastos`: encargo con decoración 25000; POST gasto `{"descripcion": "Fondant y topper", "monto": 9000, "metodo_pago_id": Efectivo, "fuente": "caja"}` → 201, `decoracion_cobrada == 25000`, `gasto_decoracion == 9000`, un `gastos_decoracion`; `GET /gastos` lo trae con `categoria == "Materiales de decoración"`, `encargo_id == encargo id`, `encargo_numero == numero`; movimientos de caja incluyen `("gasto", "Efectivo", -9000)`.
  - `test_gasto_anulado_no_cuenta`: anular por `POST /gastos/{id}/anular` → `gasto_decoracion == 0`, el gasto sigue en la lista con estado `anulado`.
  - `test_gasto_en_encargo_cancelado_o_entregado`: se permite registrar sobre encargo cancelado y entregado (201); al cancelar, los gastos previos siguen `registrado`.
  - `test_cajero_solo_desde_la_caja`: con un usuario con solo `gastos.crear_caja` (usar el fixture de cajero que ya usen `test_gastos.py`), `fuente: "banco"` → 403; `fuente: "caja"` → 201.
  - `test_encargo_de_otra_sede_no_existe` no hace falta si `obtener` ya filtra; omitir.
- [ ] **Step 2:** correr → FAIL.
- [ ] **Step 3:** implementar según Interfaces. `registrar_gasto` usa `obtener` (sin exigir estado activo), arma `GastoCrear(categoria_id=categoria_decoracion(...).id, ...)` y llama `gastos.crear(..., encargo_id=encargo.id)`; auditar `"gasto_decoracion"`. `salida` de encargos consulta los gastos con `Gasto.encargo_id == e.id`. `gastos.salida` llena `encargo_numero` si hay `encargo_id`.
- [ ] **Step 4:** correr el archivo, `tests/test_gastos.py`, `tests/test_encargos.py` → PASS.
- [ ] **Step 5: Commit** `feat(encargos): gastos de materiales de decoración ligados al encargo`.

### Task 4: Formulario del encargo con decoración

**Files:**
- Modify: `frontend/src/lib/tipos.ts` (Encargo, Gasto)
- Modify: `frontend/src/pages/encargos/FormEncargo.tsx`

**Interfaces:**
- Produces (tipos): ítem de `Encargo` + `decoracion: string | null; decoracion_precio: number | null`; `Encargo` + `decoracion_cobrada: number; gasto_decoracion: number; gastos_decoracion: { id: string; fecha: string; descripcion: string; monto: number; fuente: FuenteGasto; estado: 'registrado' | 'anulado' }[]`; `Gasto` + `encargo_id: string | null; encargo_numero: number | null`.

- [ ] **Step 1:** `Item` del formulario gana `decorar: boolean`, `decoracion: string`, `decoracionPrecio: number | null`; se precargan desde el encargo al editar.
- [ ] **Step 2:** bajo cada ítem, si `!decorar` un botón secundario `"＋ Decoración"`; si `decorar`, una fila con `Campo` "Referencia de la decoración" (maxLength 200, placeholder "Ej.: letras doradas y topper de foto"), `CampoDinero` "Valor de la decoración" y botón "Quitar decoración" (`aria-label` con el número de ítem).
- [ ] **Step 3:** `subtotalItem` suma `decoracionPrecio` cuando `decorar`; error de ítems: si `decorar` y falta referencia o valor (> 0) → `"La decoración necesita referencia y valor."`. El cuerpo envía `decoracion`/`decoracion_precio` (null si `!decorar`).
- [ ] **Step 4:** `npx tsc --noEmit` y `npx eslint src/pages/encargos src/lib/tipos.ts` → sin errores.
- [ ] **Step 5: Commit** `feat(encargos): agregar decoración a cada ítem del formulario`.

### Task 5: Detalle del encargo y de Gastos

**Files:**
- Modify: `frontend/src/pages/encargos/DetalleEncargo.tsx`
- Modify: `frontend/src/pages/encargos/Dialogos.tsx` (nuevo `DialogoGastoDecoracion`)
- Modify: `frontend/src/pages/gastos/Gastos.tsx` (`DetalleGasto`)

**Interfaces:**
- Consumes: tipos de Task 4; `POST /encargos/{id}/gastos` (Task 3).
- Produces: `DialogoGastoDecoracion({ encargo, abierto, alCerrar })`.

- [ ] **Step 1:** en la lista de ítems de `DetalleEncargo`, mostrarla también si algún ítem tiene decoración; bajo cada ítem decorado una línea `Decoración: <referencia>` con su valor.
- [ ] **Step 2:** si `decoracion_cobrada > 0` o hay `gastos_decoracion`, bloque "Decoración" con filas Cobrado / Gastado en materiales / Diferencia (`pesos`), la lista de gastos (anulados tachados) y botón secundario "Registrar gasto de decoración" visible si el usuario `puede('gastos.crear')` o `puede('gastos.crear_caja')`.
- [ ] **Step 3:** `DialogoGastoDecoracion`: campos "Qué se compró" (3–200), "Valor" (`CampoDinero`), método de pago (mismo grupo de radios que `DialogoAbono`), "De dónde sale la plata" (Caja / Banco / Dueños; sin `gastos.crear` solo Caja; si la caja está cerrada, Caja deshabilitada con aviso). Envía con idempotencia; al guardar invalida `['encargos']`, `['gastos']`, `['caja']` y avisa "Gasto de decoración registrado.".
- [ ] **Step 4:** `DetalleGasto`: si `encargo_numero`, fila "Encargo" con `Link` a `/encargos?numero=<n>` (o la ruta que use la pantalla de encargos para abrir uno; si no hay, texto "Encargo n.º 0007").
- [ ] **Step 5:** `npx tsc --noEmit`, `npx eslint .`, `npx vitest run --globals` → OK.
- [ ] **Step 6: Commit** `feat(encargos): resumen de decoración y gastos de materiales en el detalle`.

### Task 6: Prueba de punta a punta y verificación

**Files:**
- Modify: `frontend/e2e/encargos.spec.ts`

- [ ] **Step 1:** nueva prueba: crear encargo con producto de la carta + "＋ Decoración" (referencia y valor), ver el total; en el detalle registrar un gasto de decoración desde la caja y ver Cobrado / Gastado / Diferencia; alistar y entregar; en el comprobante ver la línea "Decoración: …".
- [ ] **Step 2:** `npx playwright test e2e/encargos.spec.ts --reporter=line` → PASS (escritorio y celular).
- [ ] **Step 3:** suite completa: backend `ruff check`, `ruff format --check`, `pytest` y `PGTZ=UTC pytest`; frontend `eslint`, `vitest`, `playwright test` → todo verde.
- [ ] **Step 4:** captura del formulario y del detalle (escritorio y celular) y revisar que siga el estilo del mockup de encargos.
- [ ] **Step 5: Commit** `test(encargos): decoración y gasto de materiales de punta a punta`; `git push`; esperar CI del PR #61 en verde; actualizar la descripción del PR con la sección "Decoración".
