# Zuqui's — Especificación del sistema contable e inventario

Oct 16, 2026 · @Luciano

## 1. Introducción y alcance

Zuqui's tendrá un sistema web propio para vender, controlar la caja, llevar inventario de insumos y productos, y gestionar encargos con abono. El inventario es el motivo principal del proyecto. Funcionará primero en un solo PC del local y quedará listo para servidor, celular y más sedes.

**Contexto del negocio.** Zuqui's Repostería es una pastelería y café que funciona desde 2020. Tiene punto físico en la Cra 11 Calle 17-87, Barrio El Carmen, y atiende de 3:00 a 9:00 p. m. Vende panadería, postres, tortas por encargo, bebidas calientes y frías, sodas saborizadas y malteadas. El sistema lo usan los dueños y los empleados.

**Objetivos**

- Saber en todo momento cuánto se vende, cuánto se gasta y cuánto queda, por día y por periodo.
- Controlar el inventario de insumos y productos terminados, con costo real por lote (PEPS), mermas y vencimientos.
- Conocer el costo y la ganancia de cada producto a partir de su receta.
- Gestionar encargos con abonos y saldos sin perder el control del dinero recibido.
- Cuadrar la caja diaria con arqueo y responsables identificados.

**Dentro del alcance:** carta y recetas, punto de venta, caja, gastos, compras y proveedores, inventario, producción, encargos y abonos, domicilios, propinas, descuentos, reportes, usuarios y roles configurables.

**Fuera del alcance de esta versión**

- Facturación electrónica DIAN. El negocio factura, pero por ahora el sistema hace solo control interno. Se deja preparado para integrarse con un proveedor autorizado.
- Contabilidad formal de partida doble. El sistema clasifica ingresos y egresos con un código PUC opcional para exportar al contador.
- Nómina.
- Integración con apps de domicilio (Rappi u otras).

## 2. Usuarios y roles

Los permisos se asignan por roles configurables. El administrador puede crear, editar, desactivar y duplicar roles, marcando permisos uno a uno. El sistema trae cuatro roles base que se pueden modificar, pero no eliminar mientras tengan usuarios asignados.

Cada permiso es una clave modulo.accion (por ejemplo ventas.anular o inventario.ajustar). Un usuario puede tener más de un rol y recibe la unión de sus permisos.

| Permiso | Dueño / Admin | Cajero / Vendedor | Producción / Cocina | Contador |
|---|---|---|---|---|
| Vender, cobrar, registrar propinas | Sí | Sí | No | No |
| Abrir y cerrar caja | Sí | Sí | No | No |
| Aplicar descuentos y cortesías | Sí | Hasta el tope configurado | No | No |
| Anular ventas y abonos | Sí | No | No | No |
| Crear encargos y recibir abonos | Sí | Sí | No | No |
| Decidir devolución de abonos | Sí | No | No | No |
| Registrar gastos | Sí | Solo gastos de caja | No | No |
| Registrar compras e ingreso de insumos | Sí | No | Sí | No |
| Registrar producción, mermas y ajustes | Sí | No | Sí (ajustes: no) | No |
| Editar carta, precios y recetas | Sí | No | Solo recetas | No |
| Ver reportes y exportar | Sí | Solo su caja del día | Solo inventario | Sí |
| Usuarios, roles y configuración | Sí | No | No | No |

La tabla define los valores por defecto de cada rol; el administrador puede cambiarlos. El tope de descuento de cada rol también lo define el administrador, en Configuración.

## 3. Requerimientos funcionales

Cada requerimiento tiene un código para trazarlo en el desarrollo y las pruebas.

### 3.1 Carta y productos

- **RF-01** Crear, editar y desactivar categorías con orden e ícono (Panadería, Salado, Saludable, Heladería, Bebidas calientes, Bebidas frías y granizados, Café frío, Sodas, Otras bebidas, Malteadas, Dulcería, Adiciones).
- **RF-02** Crear productos con nombre, categoría, precio de venta, foto opcional y estado disponible o agotado.
- **RF-03** Marcar cada producto como **preparado al momento** (descuenta su receta al venderse) o **producido por lote** (tiene stock propio de unidades en vitrina).
- **RF-04** Definir adiciones y modificadores con precio (por ejemplo, adición de queso mozzarella o bola de helado). Pueden tener receta propia.
- **RF-05** Guardar el historial de cambios de precio con fecha y usuario.

### 3.2 Recetas y costeo

- **RF-06** Definir la receta de cada producto: insumos, cantidad y unidad, y rendimiento (cuántas unidades produce).
- **RF-07** Calcular el costo teórico del producto con el costo actual de sus insumos y mostrar el margen frente al precio de venta. El costo actual de un insumo es su **último costo de compra** (lo que cuesta reponerlo hoy). Es solo una referencia para fijar precios; el costo real de ventas y producciones sale por PEPS (RF-08).
- **RF-08** Calcular el costo real de cada venta o producción con los lotes consumidos (PEPS).

### 3.3 Punto de venta

- **RF-09** Vender desde una cuadrícula de productos por categoría, con búsqueda, carrito, cantidades, notas y adiciones.
- **RF-10** Cobrar con uno o varios métodos de pago en la misma venta. Los métodos se configuran; hoy son efectivo y transferencias (Nequi, Bre-B, Bancolombia u otros bancos), ninguno con comisión. En efectivo se calcula el cambio.
- **RF-11** Aplicar descuentos por ítem o por venta (valor o porcentaje) y cortesías, con motivo obligatorio y usuario que autoriza.
- **RF-12** Registrar la propina aparte del valor de la venta y del método con que se pagó. No es ingreso del negocio.
- **RF-13** Marcar la venta como **en local, para llevar o domicilio**. En domicilio se registran cliente, dirección, teléfono, valor del domicilio y domiciliario. El valor del domicilio es del domiciliario, no del negocio.
- **RF-14** Generar un comprobante interno en PDF, para imprimir desde el navegador en cualquier impresora o enviar por WhatsApp. No es factura electrónica. Queda preparado para impresora térmica cuando el local la tenga.
- **RF-15** Anular una venta con motivo, sin borrarla. La anulación revierte inventario y caja.
- **RF-16** Impedir vender un producto por lote sin stock, o un preparado cuyos insumos no alcanzan, salvo que el administrador lo permita en configuración. Si lo permite, la parte que no alcanza queda como **faltante por regularizar** (tabla faltantes_inventario) con costo estimado al último costo de compra; el stock nunca queda negativo. El faltante se cuadra con la siguiente compra o producción del ítem, o con un ajuste, y aparece en las alertas de inventario mientras esté abierto.

### 3.4 Caja

- **RF-17** Abrir caja con base inicial y usuario responsable. Sin caja abierta no se puede vender ni recibir abonos.
- **RF-18** Registrar entradas y salidas de efectivo que no son ventas (pago a proveedor desde caja, retiro de los dueños), con motivo.
- **RF-19** Cerrar caja con arqueo. Antes de contar, el cierre liquida los domicilios de la sesión: muestra cuánto se le debe a cada domiciliario y registra la entrega. Luego el sistema calcula lo esperado por método de pago y el usuario digita lo contado. Se guarda la diferencia con una observación.
- **RF-20** Consultar el historial de cierres y reimprimir el resumen de cada uno.

### 3.5 Gastos

- **RF-21** Registrar gastos con fecha, categoría, descripción, valor, método de pago, proveedor opcional y foto del soporte.
- **RF-22** Configurar categorías de gasto con código PUC opcional.
- **RF-23** Indicar si el gasto sale de la caja del día o de otra fuente (cuenta bancaria, dueños).

### 3.6 Compras y proveedores

- **RF-24** Registrar proveedores con nombre, NIT o cédula, teléfono e insumos que suministra.
- **RF-25** Registrar compras de insumos. Cada línea crea un lote con cantidad, costo unitario, fecha de compra y fecha de vencimiento opcional.
- **RF-26** Indicar si la compra se pagó de contado o queda como cuenta por pagar, y registrar sus pagos.

### 3.7 Inventario y producción

- **RF-27** Llevar stock de insumos por lote, con unidad base (g, ml o unidad) y conversión desde la unidad de compra (bulto, kg, litro, paquete).
- **RF-28** Consumir lotes por PEPS al vender preparados, al producir y al registrar mermas.
- **RF-29** Registrar producción por lote: producto, cantidad producida, responsable y fecha de vencimiento. Descuenta los insumos de la receta y crea stock del producto terminado con su costo.
- **RF-30** Registrar mermas de insumos o productos terminados con motivo (vencido, dañado, error de preparación, degustación).
- **RF-31** Hacer ajustes por conteo físico con motivo y usuario. Requieren permiso de administrador.
- **RF-32** Alertar por stock bajo el mínimo configurado y por lotes próximos a vencer (días configurables).
- **RF-33** Consultar el kardex de cada insumo y producto: cada entrada y salida con su origen, lote, cantidad y costo.

### 3.8 Encargos y abonos

- **RF-34** Crear encargos con cliente, descripción, productos o detalle personalizado, fecha y hora de entrega, valor total y observaciones.
- **RF-35** Registrar uno o varios abonos con método de pago. Cada abono entra a la caja abierta en ese momento.
- **RF-36** Mostrar el saldo pendiente y cobrarlo al entregar, como cierre del encargo.
- **RF-37** Manejar los estados del encargo: pendiente, en producción, listo, entregado y cancelado.
- **RF-38** Al cancelar, por defecto se devuelve el abono completo. Como excepción, el administrador puede retener una parte o todo, con motivo obligatorio. La devolución sale como egreso de caja.
- **RF-39** Ver los encargos en calendario y en lista por fecha de entrega, con aviso de los del día.

### 3.9 Clientes

- **RF-40** Registrar clientes con nombre, teléfono y dirección para encargos y domicilios, y consultar su historial.

### 3.10 Reportes

- **RF-41** Mostrar un dashboard con ventas del día, gastos, utilidad estimada, ventas por método de pago, productos más vendidos, encargos del día y alertas de inventario.
- **RF-42** Generar reportes por rango de fechas: ventas, gastos, flujo de caja, utilidad por producto, inventario valorizado, mermas, propinas, domicilios, descuentos y cortesías, y cierres de caja.
- **RF-43** Exportar los reportes a Excel y PDF, incluido un reporte de movimientos con código PUC para el contador.

### 3.11 Configuración

- **RF-44** Configurar datos del negocio (nombre, logo, NIT, dirección), métodos de pago, categorías, unidades, tope de descuento por rol, días de alerta de vencimiento y la regla de venta sin stock.
- **RF-45** Administrar usuarios y roles según la sección 2.
- **RF-46** Dejar parámetros de impuestos configurables y desactivados por defecto, para la integración futura con facturación electrónica.

## 4. Requerimientos no funcionales

| Código | Requerimiento | Criterio de aceptación |
|---|---|---|
| RNF-01 | Exactitud del dinero | Ningún valor monetario ni cantidad se guarda ni se calcula como float (sección 6) |
| RNF-02 | Responsive y PWA | Usable desde 360 px de ancho; instalable en Android y iOS desde el navegador |
| RNF-03 | Rendimiento del POS | Agregar un producto al carrito responde en menos de 200 ms; registrar una venta, en menos de 1 s en red local |
| RNF-04 | Despliegue | Funciona en un PC del local y se traslada a un servidor sin cambios de código, solo de configuración |
| RNF-05 | Varias sedes | Todas las tablas operativas llevan sede_id desde el inicio, aunque haya una sola sede |
| RNF-06 | Sin conexión | Fase posterior: el POS sigue vendiendo sin internet y sincroniza al reconectar. La arquitectura lo deja preparado desde el inicio |
| RNF-07 | Zona horaria | Fechas guardadas en UTC y mostradas en America/Bogota. El día contable se define por la caja, no por la medianoche |
| RNF-08 | Respaldos | Copia automática diaria de la base de datos, con retención de 30 días y copia fuera del PC |
| RNF-09 | Integridad | Ningún movimiento contable o de inventario se borra; se anula o se compensa (sección 8) |
| RNF-10 | Idioma y formato | Interfaz en español; pesos con separador de miles ($12.500) y fechas dd/mm/aaaa |
| RNF-11 | Accesibilidad | Contraste mínimo AA en textos y cifras; botones del POS de al menos 44 px |

## 5. Arquitectura y stack

El sistema separa un frontend React instalable como PWA de una API en FastAPI con PostgreSQL. El mismo despliegue en Docker corre en el PC del local y luego en un servidor, sin cambios de código.

*Diagrama: cliente (React PWA) → API (FastAPI) → base de datos (PostgreSQL)*

Los routers solo validan y autorizan. Las reglas de negocio (PEPS, caja, encargos) viven en la capa de servicios, y el acceso a datos en los repositorios.

| Capa | Tecnología | Uso |
|---|---|---|
| Frontend | React + Vite + TypeScript, React Router, TanStack Query, Tailwind CSS, vite-plugin-pwa, decimal.js | Interfaz responsive, caché de datos, instalación en celular, operaciones decimales |
| Backend | Python 3.12 o superior, FastAPI, Pydantic v2, Uvicorn | API REST con validación y documentación OpenAPI |
| Datos | PostgreSQL 16 o superior, SQLAlchemy 2, Alembic | Tipos exactos (NUMERIC, BIGINT) y migraciones versionadas |
| Seguridad | PyJWT, argon2-cffi | Tokens y hash de contraseñas |
| Reportes | openpyxl, WeasyPrint | Exportación a Excel y PDF |
| Pruebas | pytest, httpx, Vitest, Playwright | Sección 13 |
| Infraestructura | Docker Compose, Caddy, GitHub Actions | Despliegue, HTTPS e integración continua |

**Estructura del repositorio**

```text
zuquis/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/          # configuración, base de datos, seguridad, permisos
│   │   ├── shared/        # dinero.py (Decimal y redondeo), errores, paginación
│   │   └── modules/
│   │       ├── auth/      # router.py · schemas.py · service.py · models.py
│   │       ├── carta/
│   │       ├── inventario/
│   │       ├── compras/
│   │       ├── produccion/
│   │       ├── ventas/
│   │       ├── caja/
│   │       ├── gastos/
│   │       ├── encargos/
│   │       └── reportes/
│   ├── migrations/        # Alembic
│   └── tests/
├── frontend/
│   └── src/
│       ├── api/           # cliente HTTP y tipos
│       ├── features/      # pos, caja, inventario, encargos, reportes…
│       ├── components/
│       └── theme/         # tokens de marca (sección 10)
├── docker-compose.yml
└── .github/workflows/
```

Cada módulo del backend tiene las mismas cuatro piezas, para que un módulo nuevo se agregue sin tocar los demás.

## 6. Manejo de dinero y cantidades

Ningún valor de dinero o inventario se guarda ni se calcula como float. Los montos en pesos van como enteros, y los costos unitarios y las cantidades como decimales exactos. float no representa decimales de forma exacta (0.1 + 0.2 = 0.30000000000000004), y en arqueos e inventario el error se acumula.

| Tipo de valor | Ejemplos | PostgreSQL | Python | Frontend y JSON |
|---|---|---|---|---|
| Monto en pesos | Precio de venta, total, pago, abono, gasto, propina, domicilio | BIGINT (pesos enteros) | int | Número entero |
| Costo unitario | Costo por gramo de harina, costo por unidad producida | NUMERIC(18,6) | Decimal | String ("4.200000") |
| Cantidad de inventario | 250 g, 0,5 L, 12 unidades | NUMERIC(18,4) | Decimal | String |
| Porcentaje | Descuento, impuesto futuro | NUMERIC(7,4) | Decimal | String |

**Reglas**

- Los montos en pesos no tienen centavos: $12.500 se guarda como 12500.
- Los decimales viajan como string en la API para que JavaScript no los convierta a float. En el frontend se operan con una librería decimal (por ejemplo decimal.js) o solo se muestran.
- El costo de una línea se calcula en Decimal (cantidad × costo unitario) y se redondea a peso entero **una sola vez**, al guardar el movimiento, con ROUND_HALF_UP.
- Los porcentajes se aplican en Decimal y el resultado se redondea a peso con la misma regla.
- Los totales se calculan sumando líneas ya redondeadas, para que el total siempre cuadre con el detalle.
- En SQLAlchemy se usa Numeric(asdecimal=True) y en Pydantic Decimal con max_digits y decimal_places. Se prohíbe Float con una regla de revisión de código y una prueba automática.

## 7. Modelo de datos

El modelo se organiza alrededor de dos libros que nunca se editan: **caja_movimientos** para el dinero y **movimientos_inventario** para las existencias. Ventas, abonos, gastos, compras, producción y mermas solo escriben en ellos.

**Campos comunes en todas las tablas operativas:** id (UUID), sede_id, creado_en, creado_por, actualizado_en. Los montos son BIGINT en pesos y las cantidades y costos unitarios son NUMERIC (sección 6).

### 7.1 Seguridad y configuración

| Tabla | Campos principales | Notas |
|---|---|---|
| sedes | nombre, direccion, telefono, activa | Una sede al inicio |
| usuarios | nombre, email, password_hash, pin_hash, activo, ultimo_acceso, intentos_fallidos, bloqueado_hasta | pin_hash para el cambio rápido de cajero (sección 11) |
| sesiones_refresh | usuario_id, token_hash, expira_en, revocado_en, reemplazado_por | Rotación y revocación del token de renovación |
| roles | nombre, descripcion, es_base | Roles base no eliminables si tienen usuarios |
| permisos | clave (ventas.anular), descripcion, modulo | Catálogo fijo definido en código |
| rol_permisos | rol_id, permiso_id |  |
| usuario_roles | usuario_id, rol_id, sede_id | Permite roles distintos por sede |
| configuracion | sede_id, clave, valor (JSONB) | Topes, alertas, reglas de venta sin stock |
| auditoria | usuario_id, accion, entidad, entidad_id, antes (JSONB), despues (JSONB), fecha, ip | Sección 11 |
| idempotencia | clave, usuario_id, ruta, hash_cuerpo, estado_http, respuesta (JSONB), creado_en, expira_en | Encabezado Idempotency-Key (sección 9) |
| consecutivos | sede_id, tipo (venta / encargo), ultimo | Se lee con bloqueo de fila; los números no se reutilizan (RN-04) |

### 7.2 Carta y recetas

| Tabla | Campos principales | Notas |
|---|---|---|
| categorias | nombre, orden, icono, activa |  |
| productos | categoria_id, nombre, tipo (preparado / lote), precio, foto_url, disponible, activo, stock_minimo, dias_vida_util | precio en BIGINT |
| modificadores | nombre, precio, activo | Adiciones como queso o bola de helado |
| producto_modificadores | producto_id, modificador_id | Qué adiciones admite cada producto |
| precios_historial | producto_id, precio_anterior, precio_nuevo, usuario_id, fecha |  |
| recetas | producto_id o modificador_id, rendimiento (NUMERIC), version, vigente | Se versionan para no alterar costos pasados |
| receta_items | receta_id, insumo_id, cantidad (NUMERIC) | Cantidad en la unidad base del insumo |

### 7.3 Inventario, compras y producción

| Tabla | Campos principales | Notas |
|---|---|---|
| unidades | codigo (g, ml, und), nombre |  |
| insumos | nombre, unidad_base, stock_minimo, dias_alerta_vencimiento, activo |  |
| presentaciones | insumo_id, nombre ("Bulto 50 kg"), factor (NUMERIC) | Convierte la unidad de compra a la unidad base |
| lotes | tipo_item (insumo / producto), item_id, origen (compra / produccion / ajuste), origen_id, cantidad_inicial, cantidad_disponible, costo_unitario NUMERIC(18,6), fecha_ingreso, fecha_vencimiento | Base de PEPS y vencimientos |
| movimientos_inventario | tipo, tipo_item, item_id, lote_id, cantidad (con signo), costo_unitario, costo_total (BIGINT), referencia_tipo, referencia_id, usuario_id, fecha | Libro de inventario; solo inserciones |
| proveedores | nombre, nit_o_cedula, telefono, email, activo |  |
| proveedor_insumos | proveedor_id, insumo_id | Insumos que suministra cada proveedor (RF-24) |
| faltantes_inventario | tipo_item, item_id, cantidad, costo_estimado, venta_id, estado (abierto / regularizado), regularizado_por_mov_id | Ventas sin stock permitidas por el admin (RF-16) |
| compras | proveedor_id, fecha, numero_factura_proveedor, total, estado_pago (contado / por_pagar / pagada), soporte_url |  |
| compra_items | compra_id, insumo_id, presentacion_id, cantidad, costo_total, fecha_vencimiento | Cada ítem crea un lote |
| pagos_compra | compra_id, fecha, monto, metodo_pago_id, caja_sesion_id (opcional) |  |
| producciones | producto_id, receta_id, cantidad_producida, costo_total, lote_resultante_id, responsable_id, fecha |  |
| mermas | tipo_item, item_id, lote_id, cantidad, motivo, costo_total, usuario_id |  |
| ajustes_inventario | tipo_item, item_id, cantidad_sistema, cantidad_contada, diferencia, motivo, aprobado_por |  |

Tipos de movimientos_inventario: compra, venta, consumo_produccion, entrada_produccion, merma, ajuste y reverso_anulacion.

### 7.4 Ventas, caja y gastos

| Tabla | Campos principales | Notas |
|---|---|---|
| metodos_pago | nombre, es_efectivo, titular (negocio / dueno), cuenta_puc, activo, orden | Efectivo, Nequi, Bre-B, Bancolombia, otra transferencia. Hay cuentas del negocio y cuentas personales de los dueños; titular y cuenta_puc se configuran por método |
| caja_sesiones | abierta_por, abierta_en, base_inicial, cerrada_por, cerrada_en, estado, observacion |  |
| caja_arqueos | caja_sesion_id, metodo_pago_id, esperado, contado, diferencia | Una fila por método al cerrar |
| caja_movimientos | caja_sesion_id, tipo, metodo_pago_id, monto (con signo), referencia_tipo, referencia_id, motivo, usuario_id, fecha | Libro de dinero; solo inserciones |
| ventas | numero (consecutivo por sede), caja_sesion_id, tipo_servicio (local / llevar / domicilio), cliente_id, subtotal, descuento_total, valor_domicilio, total, propina, estado (pagada / anulada), motivo_anulacion, anulada_por, descuento_motivo, descuento_autorizado_por |  |
| venta_items | venta_id, producto_id, cantidad, precio_unitario, descuento, subtotal, costo_total, nota | Copia el precio del momento |
| venta_item_modificadores | venta_item_id, modificador_id, precio, costo_total |  |
| venta_pagos | venta_id, metodo_pago_id, monto | La suma cubre total + propina + domicilio |
| domiciliarios | nombre, telefono, activo | No son usuarios del sistema; se eligen al vender y se les liquida al cierre |
| domicilios | venta_id o encargo_id, direccion, telefono, domiciliario_id, valor, estado, liquidado_en | El valor es del domiciliario (RN-18) |
| categorias_gasto | nombre, cuenta_puc, activa |  |
| gastos | fecha, categoria_id, descripcion, monto, metodo_pago_id, fuente (caja / banco / duenos), caja_sesion_id, proveedor_id, soporte_url, estado |  |

Tipos de caja_movimientos: venta, propina, domicilio, pago_domiciliario, abono, saldo_encargo, devolucion_abono, gasto, pago_compra, entrada_manual, salida_manual y reverso_anulacion.

### 7.5 Clientes y encargos

| Tabla | Campos principales | Notas |
|---|---|---|
| clientes | nombre, telefono, direccion, notas |  |
| encargos | numero (consecutivo por sede), cliente_id, descripcion, fecha_entrega, total, estado, venta_id (al entregar), decision_cancelacion (retiene / devuelve_total / devuelve_parcial), monto_devuelto, motivo_cancelacion, cancelado_por |  |
| encargo_items | encargo_id, producto_id (opcional), descripcion, cantidad, precio | Permite ítems personalizados sin producto |
| encargo_abonos | encargo_id, monto, metodo_pago_id, caja_sesion_id, estado |  |

## 8. Reglas de negocio

Toda operación que mueve dinero o inventario se ejecuta en **una sola transacción** de base de datos. Si una parte falla, no se guarda nada.

### 8.1 Integridad contable

- **RN-01** Ventas, abonos, gastos, compras, producciones y mermas no se borran. Se anulan con motivo, usuario y fecha, y la anulación crea movimientos inversos en caja e inventario.
- **RN-02** Una venta o un abono solo se registra con una caja abierta, y queda ligado a ella.
- **RN-03** Una caja cerrada no admite movimientos. Una anulación posterior al cierre se registra en la caja abierta del día en que se anula.
- **RN-04** El consecutivo de ventas es único por sede y no se reutiliza, ni siquiera tras una anulación.

### 8.2 Inventario y costeo PEPS

- **RN-05** Las salidas de inventario consumen primero el lote con fecha de ingreso más antigua y cantidad disponible. Si un movimiento necesita más de lo que tiene un lote, se reparte entre varios lotes y se registra una fila por lote.
- **RN-06** Al vender un producto **preparado**, se descuentan los insumos de su receta vigente y de sus adiciones multiplicados por la cantidad vendida. El costo de la venta es la suma del costo de los lotes consumidos.
- **RN-07** Al registrar una **producción por lote**, se descuentan los insumos de la receta según la cantidad producida. Se crea un lote del producto terminado con costo unitario igual al costo total consumido dividido entre las unidades producidas.
- **RN-08** Al vender un producto **por lote**, se descuentan unidades del lote terminado más antiguo (PEPS). El costo de la venta sale de ese lote.
- **RN-09** El stock de un ítem es la suma de cantidad_disponible de sus lotes. movimientos_inventario es la fuente de verdad, y una tarea de verificación compara ambos cada noche.
- **RN-10** Una merma o ajuste negativo consume lotes por PEPS. Un ajuste positivo crea un lote de origen ajuste con el costo del último lote del ítem.
- **RN-11** Un lote vencido queda bloqueado para venta y producción hasta que se registre como merma.
- **RN-12** La anulación de una venta devuelve las cantidades **a los mismos lotes** de donde salieron, con su costo original.

### 8.3 Caja y arqueo

- **RN-13** Al cerrar caja, el valor esperado por método de pago es la base inicial (solo en efectivo) más la suma de caja_movimientos de la sesión para ese método.
- **RN-14** La diferencia entre lo contado y lo esperado se guarda tal cual, sin ajustes automáticos, y exige observación si no es cero.
- **RN-15** Las propinas entran a caja en un movimiento propio de tipo propina. No cuentan como ingreso en los reportes de ventas ni de utilidad.

### 8.4 Descuentos y domicilios

- **RN-16** Un descuento por encima del tope que el administrador configuró para el rol del usuario requiere que un administrador lo autorice con su credencial en el mismo momento.
- **RN-17** Una cortesía es un descuento del 100 %. Descuenta inventario normalmente y su costo se reporta como gasto de cortesía.
- **RN-18** El valor del domicilio es del domiciliario, no del negocio. Se cobra junto con la venta, pero entra a caja como movimiento domicilio y no suma en ventas ni en utilidad. Se le entrega al domiciliario al cierre de caja: el cierre suma sus domicilios de la sesión, registra una salida pago_domiciliario por ese total y marca cada domicilio con la fecha en liquidado_en. No se puede cerrar la caja con domicilios sin liquidar.

### 8.5 Encargos y abonos

- **RN-19** La suma de abonos no puede superar el total del encargo.
- **RN-20** Cada abono entra como movimiento abono en la caja abierta. En los reportes de caja cuenta como ingreso de dinero el día que se recibe; en los de ventas y utilidad cuenta el día que se entrega el encargo.
- **RN-21** Al entregar, se cobra el saldo, se crea la venta asociada y se descuenta el inventario. Los abonos previos quedan aplicados a esa venta.
- **RN-22** Al cancelar, la opción por defecto es devolver el total del abono. Solo un administrador puede elegir, como excepción, devolver parcial o retener, con motivo obligatorio. Lo devuelto sale de la caja abierta como devolucion_abono. Lo retenido se reporta como ingreso por cancelación, aparte de las ventas, y no suma en ventas ni en utilidad por producto.
- **RN-23** Un encargo en estado en produccion ya no se puede editar. Si alguien lo intenta, el sistema le informa que el encargo está en producción y que solo un administrador puede cancelarlo.

## 9. API REST

La API es REST con JSON y está versionada bajo /api/v1. FastAPI genera la documentación OpenAPI automáticamente en /docs. Todas las rutas, salvo el login, exigen token y validan el permiso correspondiente.

**Convenciones**

- Listados paginados con ?page=&size= y filtros por fecha ?desde=&hasta= en formato ISO.
- Montos como enteros; costos y cantidades como string decimal (sección 6).
- Las operaciones que mueven dinero o inventario aceptan un encabezado Idempotency-Key. Así, si el POS reintenta por una falla de red, la venta no se duplica; también prepara el trabajo sin conexión.
- Las anulaciones son POST /{recurso}/{id}/anular con motivo. No existe DELETE sobre movimientos.
- Los errores siguen un formato único: {"codigo": "STOCK_INSUFICIENTE", "mensaje": "…", "detalle": {…}}.

| Módulo | Endpoints principales |
|---|---|
| Autenticación | POST /auth/login · POST /auth/refresh · POST /auth/logout · GET /auth/me |
| Usuarios y roles | GET/POST /usuarios · PATCH /usuarios/{id} · GET/POST /roles · PATCH /roles/{id} · GET /permisos |
| Carta | GET/POST /categorias · GET/POST /productos · PATCH /productos/{id} · GET/POST /modificadores · GET /productos/{id}/costo |
| Recetas | GET/PUT /productos/{id}/receta · GET /productos/{id}/receta/versiones |
| Insumos | GET/POST /insumos · PATCH /insumos/{id} · GET /insumos/{id}/lotes · GET /insumos/{id}/kardex |
| Compras | GET/POST /proveedores · GET/POST /compras · POST /compras/{id}/pagos · POST /compras/{id}/anular |
| Producción | GET/POST /producciones · POST /producciones/{id}/anular |
| Inventario | GET /inventario/stock · GET /inventario/alertas · POST /mermas · POST /ajustes · GET /inventario/movimientos |
| Caja | GET /caja/actual · POST /caja/abrir · POST /caja/movimientos · POST /caja/cerrar · GET /caja/sesiones · GET /caja/sesiones/{id} |
| Ventas | POST /ventas · GET /ventas · GET /ventas/{id} · POST /ventas/{id}/anular · GET /ventas/{id}/comprobante |
| Domicilios | GET /domicilios · PATCH /domicilios/{id}/estado |
| Gastos | GET/POST /gastos · POST /gastos/{id}/anular · GET/POST /categorias-gasto |
| Clientes | GET/POST /clientes · PATCH /clientes/{id} · GET /clientes/{id}/historial |
| Encargos | GET/POST /encargos · PATCH /encargos/{id} · POST /encargos/{id}/abonos · POST /encargos/{id}/estado · POST /encargos/{id}/entregar · POST /encargos/{id}/cancelar |
| Reportes | GET /reportes/dashboard · GET /reportes/{tipo}?desde=&hasta=&formato=json\|xlsx\|pdf |
| Configuración | GET/PATCH /configuracion · GET/POST /metodos-pago · GET/POST /sedes |
| Archivos | POST /archivos (soportes y fotos; devuelve la URL) |

## 10. Interfaz y línea visual

La interfaz toma la identidad de Zuqui's (rosa pastel, dorado, serif elegante, detalles florales) para el marco de la aplicación. Las áreas de trabajo y las cifras van limpias y legibles. Se diseña primero para celular y luego se adapta a escritorio.

**Mockups de referencia:** las pantallas se construyen recreando los [mockups](mockups/README.md) tal como están (estructura, textos, colores, tipografía y componentes), no solo como inspiración. Cubren dashboard, POS (escritorio y celular), cierre de caja, inventario por lotes y encargos; el resto de pantallas sigue el mismo sistema visual. Si un mockup contradice esta especificación, se resuelve la discrepancia antes de implementar.

### 10.1 Pantallas

| Pantalla | Contenido | Roles con acceso por defecto |
|---|---|---|
| Login | Logo, usuario y contraseña, selección de sede si hay varias | Todos |
| Dashboard | Ventas, gastos y utilidad del día; métodos de pago; top de productos; encargos del día; alertas de inventario | Admin, Contador |
| POS | Categorías en pestañas, productos en tarjetas, carrito, cobro con pago mixto, propina, tipo de servicio | Admin, Cajero |
| Caja | Estado de la caja, entradas y salidas, cierre con arqueo, historial | Admin, Cajero |
| Encargos | Calendario y lista, detalle, abonos, cambio de estado, entrega y cancelación | Admin, Cajero |
| Domicilios | Lista del día por estado y domiciliario | Admin, Cajero |
| Carta | Categorías, productos, adiciones, precios | Admin |
| Recetas | Receta por producto, costo teórico y margen | Admin, Producción |
| Insumos e inventario | Stock por ítem y lote, alertas, kardex | Admin, Producción |
| Compras y proveedores | Registro de compras, lotes y cuentas por pagar | Admin, Producción |
| Producción y mermas | Registro de tandas producidas y de pérdidas | Admin, Producción |
| Gastos | Lista y formulario rápido con foto del soporte | Admin, Cajero |
| Clientes | Lista e historial | Admin, Cajero |
| Reportes | Selector de reporte, rango de fechas y exportación | Admin, Contador |
| Configuración | Negocio, sedes, métodos de pago, categorías, usuarios y roles | Admin |

### 10.2 Paleta

| Token | Color | Uso |
|---|---|---|
| --rosa | #F7C8DA | Sidebar, encabezados, fondos de marca |
| --dorado | #B8964A | Títulos, bordes finos, íconos, separadores |
| --fucsia | #C42D72 | Botón principal (cobrar, guardar), texto de acento y alertas. Contraste 5,3:1 con blanco (AA) |
| --fucsia-claro | #E2468F | Solo acentos decorativos y elementos grandes; no para texto normal (3,8:1) |
| --crema | #FFF8F4 | Fondo de las áreas de trabajo |
| --cafe | #4A3428 | Texto principal |
| --exito / --peligro | #2E7D5B / #C0392B | Estados (caja cuadrada, diferencia, stock bajo) |

Los tonos se tomaron del logo, la carta y las fotos del local, que es el material disponible. El fucsia sobre crema y el café sobre rosa deben cumplir contraste AA; el dorado no se usa para texto pequeño.

### 10.3 Tipografía y componentes

- **Títulos:** serif de estilo clásico, como Cormorant Garamond o Cinzel, en línea con el logo.
- **Texto, tablas y cifras:** sans legible, como Montserrat o Inter, con números tabulares (font-variant-numeric: tabular-nums) y alineados a la derecha.
- **Detalle caligráfico** (como el "Since 2020" del logo): solo en el login y en estados vacíos.
- Tarjetas con esquinas redondeadas y borde dorado de 1 px, como en la carta impresa del local.
- Botones del POS de al menos 44 px, para pantalla táctil.
- Un modo de alto contraste en el POS para pantallas con mucho brillo.

## 11. Seguridad y auditoría

Cada acción queda asociada a un usuario autenticado, y toda modificación sensible deja rastro de qué cambió, quién y cuándo.

**Autenticación**

- Contraseñas con hash Argon2 (o bcrypt). Nunca se guardan ni se registran en texto plano.
- Token de acceso JWT de corta duración (15 min) y token de renovación de 7 días, rotado en cada uso y revocable al cerrar sesión.
- En el navegador, el token de renovación va en cookie HttpOnly, Secure y SameSite=Strict, no en localStorage.
- Bloqueo temporal tras 5 intentos fallidos de inicio de sesión.
- Opción de PIN corto para cambiar rápido de cajero en el POS sin cerrar la sesión del equipo.

**Autorización**

- Cada endpoint declara el permiso que exige, y el backend lo valida siempre. Ocultar botones en el frontend no reemplaza esta validación.
- Los datos se filtran por sede_id según los roles del usuario.

**Auditoría**

- La tabla auditoria registra creación, edición, anulación, cambios de precio, cambios de receta, ajustes de inventario, cambios de permisos e inicios de sesión, con el estado anterior y el nuevo.
- La auditoría es de solo inserción, y solo el administrador puede consultarla.

**Infraestructura**

- HTTPS obligatorio en servidor, con certificado de Let's Encrypt.
- Secretos (clave JWT, credenciales de base de datos) en variables de entorno, nunca en el repositorio.
- Validación de entrada con Pydantic en todos los endpoints, y consultas siempre a través del ORM, sin SQL concatenado.
- Límite de peticiones en login y en endpoints públicos.
- Archivos subidos limitados a imágenes y PDF de máximo 5 MB, con nombre aleatorio.
- Datos personales de clientes tratados según la Ley 1581 de 2012 de protección de datos. Se recomienda validar con el negocio su aviso de privacidad.

## 12. Plan de desarrollo por fases

El desarrollo va en siete fases, de la 0 a la 6. El inventario se construye antes que el POS porque es la razón principal del proyecto y porque las ventas dependen de él. La duración de cada fase se fija cuando se confirmen disponibilidad y fecha de entrega (sección 14).

| Fase | Contenido | Criterio para pasar a la siguiente |
|---|---|---|
| 0. Base | Repositorio, Docker Compose, PostgreSQL, migraciones, autenticación, usuarios, roles configurables, sedes, configuración, auditoría, integración continua | Login funcional con permisos; pruebas automáticas corriendo en cada cambio |
| 1. Inventario | Categorías, productos, adiciones, insumos, unidades y presentaciones, proveedores, compras con lotes, recetas, producción, mermas, ajustes, kardex, alertas | Una compra crea lotes; una producción los consume por PEPS y crea stock terminado con costo correcto |
| 2. Venta y caja | POS, pago mixto, descuentos y cortesías, propinas, anulaciones, apertura y cierre de caja con arqueo, gastos | Un día completo de ventas cuadra en caja e inventario contra un caso de prueba calculado a mano |
| 3. Encargos y domicilios | Clientes, encargos, abonos, entrega, cancelación con decisión del admin, domicilios | Un encargo con dos abonos, entrega y una cancelación con devolución parcial quedan reflejados en caja y reportes |
| 4. Reportes | Dashboard, reportes por rango, utilidad por producto, inventario valorizado, exportación a Excel y PDF con PUC | Los reportes de una semana de datos de prueba coinciden con los cálculos de control |
| 5. Producción y salida a servidor | Instalación en el PC del local, carga de la carta e inventario inicial, capacitación, respaldos; luego servidor con HTTPS y PWA en celular | El negocio opera una semana completa solo con el sistema |
| 6. Evolución | Trabajo sin conexión en el POS, segunda sede, integración de facturación electrónica, impresora térmica, cajón monedero y lector de códigos | Se planifica según la operación real |

## 13. Pruebas y despliegue

### 13.1 Pruebas

- **Unitarias (pytest):** cálculo PEPS con varios lotes, conversión de unidades, redondeo de montos, costo de receta y arqueo de caja. Son obligatorias antes de cada fusión a la rama principal.
- **De integración:** endpoints contra una base PostgreSQL real en Docker, incluidas las transacciones que deben revertirse completas ante un error.
- **Guardia de tipos:** una prueba que recorre los modelos de SQLAlchemy y falla si encuentra una columna Float.
- **Casos contables de control:** escenarios calculados a mano (un día de ventas, una semana con compras a precios distintos, un encargo cancelado) que el sistema debe reproducir al peso.
- **Frontend:** pruebas de componentes con Vitest y flujos principales (vender, cerrar caja, registrar compra) con Playwright, en tamaño de escritorio y de celular.
- **Aceptación con el negocio:** al final de cada fase, los dueños prueban los flujos con datos reales de la carta.

### 13.2 Despliegue

| Entorno | Cómo corre | Base de datos | Notas |
|---|---|---|---|
| Desarrollo | Docker Compose en el equipo del desarrollador | PostgreSQL en contenedor | Datos de prueba con un script de semillas |
| Local del negocio | Docker Compose en el PC del local; se abre en el navegador y queda instalado como app | PostgreSQL en contenedor con volumen persistente | Respaldo diario automático con pg_dump a una carpeta sincronizada en la nube |
| Servidor | Mismo Compose en un VPS, con proxy inverso (Caddy o Nginx) y HTTPS | PostgreSQL en el VPS o administrado | Se migra restaurando el último respaldo; solo cambia la configuración |

La integración continua (GitHub Actions) ejecuta linters (Ruff, ESLint), pruebas y el build de las imágenes en cada cambio. Las migraciones de base de datos se aplican con Alembic al iniciar el contenedor de la API.

Los respaldos se prueban restaurándolos una vez al mes en un entorno aparte.

## 14. Pendientes por confirmar

Los puntos marcados se resolvieron el 16/10/2026 y ya están reflejados en el documento. Los abiertos deben cerrarse antes de la fase en que se usan.

### Con el negocio

- ☒ Entrega al domiciliario de lo cobrado por domicilios: al cierre de caja (RF-19, RN-18).
- ☒ Valor del domicilio: es ingreso del domiciliario (RN-18).
- ☒ Métodos de pago: efectivo y transferencias (Nequi, Bre-B, Bancolombia u otros), ninguno con comisión.
- ☒ Compras a crédito: se asume que sí; el sistema maneja cuentas por pagar (RF-26).
- ☒ Roles y tope de descuento: editables por el administrador en Configuración (sección 2).
- ☒ Venta sin stock: no se permite, salvo que el administrador lo active (RF-16).
- ☒ Encargo en producción: no se edita, y el sistema le informa al usuario por qué (RN-23).
- ☒ Hardware: por ahora solo el PC; impresora térmica, cajón monedero y lector quedan para la fase 6.
- ☒ Carga inicial: se hace después de aprobada la propuesta (fase 5).
- ☒ Marca: se trabaja con el material disponible (sección 10.2).
- ☒ Fecha de entrega: sin definir por ahora.

### Con el contador

- ☐ Régimen tributario y tipo de impuesto que aplica a sus ventas (IVA o impuesto al consumo), y proveedor de facturación electrónica actual. Sin definir al 17/10/2026; no bloquea hasta la fase 6.
- ☒ Costeo PEPS por lote: aprobado (17/10/2026).
- ☒ Abono en una cancelación (RN-22): por defecto se devuelve todo; si el admin retiene una parte, se reporta como ingreso por cancelación, no como venta (17/10/2026).
- ☒ Cortesías registradas como gasto por su costo (RN-17): aprobado (17/10/2026).
- ☒ Costo de los ajustes positivos de inventario (RN-10): costo del último lote (17/10/2026).
- ☐ Códigos PUC: la estructura está decidida (17/10/2026): actividad de elaboración de panadería (4120 / 6120), cuentas de 4 dígitos, mermas como gasto aparte y transferencias que llegan a cuentas del negocio o de los dueños según el método. Falta el visto bueno del contador a la tabla de [puc-propuesta.md](puc-propuesta.md).
- ☒ Propinas como dinero de terceros, fuera de los ingresos (RN-15).
- ☒ El abono cuenta como venta al entregar el encargo (RN-20).