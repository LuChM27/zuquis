import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const ADMIN = {
  email: process.env.E2E_ADMIN_EMAIL ?? 'admin@zuquis.local',
  clave: process.env.E2E_ADMIN_CLAVE ?? 'zuquis-dev-123',
}
const API = process.env.E2E_API_URL ?? 'http://localhost:8000/api/v1'

async function ingresar(page: Page) {
  await page.goto('/ingresar')
  await page.getByLabel('Correo').fill(ADMIN.email)
  await page.getByLabel('Contraseña', { exact: true }).fill(ADMIN.clave)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page).not.toHaveURL(/\/ingresar$/)
}

async function preparar(request: APIRequestContext) {
  const login = await request.post(`${API}/auth/login`, { data: { email: ADMIN.email, password: ADMIN.clave } })
  expect(login.ok(), 'el administrador de prueba debe existir (ver e2e/README.md)').toBeTruthy()
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` }
  const post = async (ruta: string, data: unknown) => {
    const r = await request.post(`${API}${ruta}`, { headers: auth, data })
    expect(r.ok(), `${ruta}: ${await r.text()}`).toBeTruthy()
    return r.json()
  }
  const caja = await (await request.get(`${API}/caja/actual`, { headers: auth })).json()
  if (!caja.abierta) await post('/caja/abrir', { base_inicial: 100000 })
  const marca = Date.now()
  const cliente = await post('/clientes', {
    nombre: `Cliente E2E ${marca}`,
    telefono: `31${String(marca).slice(-8)}`,
    permitir_telefono_repetido: true,
  })
  return { auth, post, marca, cliente }
}

test('encargo: crear con abono, pasar a producción, ya no se edita, entregar y cobrar el saldo', async ({ page, request }) => {
  const { marca, cliente } = await preparar(request)
  await ingresar(page)
  await page.goto('/encargos')
  await page.getByRole('button', { name: 'Nuevo encargo' }).click()

  const form = page.getByRole('dialog', { name: 'Nuevo encargo' })
  await form.getByRole('combobox', { name: 'Cliente' }).fill(cliente.nombre)
  await form.getByRole('option', { name: new RegExp(cliente.nombre) }).click()
  await form.getByLabel('Hora de entrega').fill('17:00')
  const item = form.getByRole('listitem', { name: 'Ítem 1' })
  await item.getByLabel('Descripción').fill(`Torta de cumpleaños E2E ${marca}`)
  await item.getByLabel('Precio c/u').fill('90000')
  await expect(form).toContainText('$90.000')
  await form.getByLabel('Valor del abono').fill('45000')
  await form.getByRole('radio', { name: 'Nequi' }).click()
  await form.getByRole('button', { name: 'Crear encargo' }).click()

  const detalle = page.getByRole('region', { name: /^Encargo n\.º/ })
  await expect(detalle.getByRole('heading', { name: `Torta de cumpleaños E2E ${marca}` })).toBeVisible()
  await expect(detalle).toContainText('Saldo por cobrar')
  await expect(detalle).toContainText('$45.000')
  await expect(detalle).toContainText('Nequi')

  await detalle.getByRole('button', { name: 'Pasar a producción' }).click()
  await expect(detalle).toContainText('Ya pasó a producción, así que no se puede editar')
  await expect(detalle.getByRole('button', { name: 'Editar encargo' })).toHaveCount(0)

  await detalle.getByRole('button', { name: 'Marcar como listo' }).click()
  await detalle.getByRole('button', { name: 'Entregar y cobrar $45.000' }).click()
  const entrega = page.getByRole('dialog', { name: 'Entregar y cobrar' })
  await entrega.getByRole('radio', { name: 'Efectivo' }).click()
  await entrega.getByRole('button', { name: 'Entregar y cobrar $45.000' }).click()

  await expect(page.getByText(/^Encargo entregado: venta n\.º/)).toBeVisible()
  await expect(detalle).toContainText('Entregado y cobrado.')
  await detalle.getByRole('link', { name: /^Venta n\.º/ }).click()
  const venta = page.locator('section').filter({ has: page.getByRole('heading', { level: 2, name: /^Venta n\.º/ }) })
  await expect(venta).toContainText(`Torta de cumpleaños E2E ${marca}`)
  await expect(venta).toContainText('Abonos ya recibidos')
  await expect(venta).toContainText('$90.000')
})

test('domicilio: vender a domicilio y entregarle al domiciliario lo suyo en el cierre', async ({ page, request }) => {
  const { auth, post, marca } = await preparar(request)
  const jarabe = await post('/insumos', { nombre: `Jarabe domicilio E2E ${marca}`, unidad_base: 'ml' })
  await post('/compras', { estado_pago: 'por_pagar', items: [{ insumo_id: jarabe.id, cantidad: '1000', costo_total: 10000 }] })
  const categoria = await post('/categorias', { nombre: `Domicilio E2E ${marca}` })
  const soda = await post('/productos', { categoria_id: categoria.id, nombre: `Soda domicilio E2E ${marca}`, tipo: 'preparado', precio: 12000 })
  const r = await request.put(`${API}/productos/${soda.id}/receta`, {
    headers: auth,
    data: { rendimiento: '1', items: [{ insumo_id: jarabe.id, cantidad: '20' }] },
  })
  expect(r.ok()).toBeTruthy()
  const domiciliario = await post('/domiciliarios', { nombre: `Mensajero E2E ${marca}` })

  await ingresar(page)
  await page.goto('/vender')
  await page.getByLabel('Buscar producto').fill(soda.nombre)
  await page.getByRole('button', { name: new RegExp(`^${soda.nombre},`) }).click()
  const venta = page.getByRole('complementary', { name: 'Venta actual' })
  await venta.getByRole('radio', { name: 'Domicilio' }).click()
  await venta.getByLabel('Dirección de entrega').fill('Calle 20 # 8-15')
  await venta.getByRole('combobox', { name: 'Domiciliario' }).fill(domiciliario.nombre)
  await venta.getByRole('option', { name: domiciliario.nombre }).click()
  await venta.getByLabel('Valor del domicilio').fill('4000')
  await venta.getByRole('button', { name: /^Efectivo/ }).click()
  await venta.getByRole('button', { name: 'Cobrar $16.000' }).click()
  await page.getByRole('dialog', { name: /^Venta n\.º/ }).getByRole('button', { name: 'Nueva venta' }).click()

  await page.goto('/encargos?seccion=domicilios')
  await expect(page.getByRole('listitem').filter({ hasText: domiciliario.nombre })).toContainText('Calle 20 # 8-15')

  await page.goto('/caja?seccion=cierre')
  const pendiente = page.getByRole('list', { name: 'Por entregar a cada domiciliario' }).getByRole('listitem').filter({ hasText: domiciliario.nombre })
  await pendiente.getByRole('button', { name: `Entregar $4.000 a ${domiciliario.nombre}` }).click()
  await expect(pendiente).toHaveCount(0)
})

test('decoración: torta con decoración, gasto de materiales ligado y línea propia en la venta', async ({ page, request }) => {
  const { marca, cliente } = await preparar(request)
  await ingresar(page)
  await page.goto('/encargos')
  await page.getByRole('button', { name: 'Nuevo encargo' }).click()

  const form = page.getByRole('dialog', { name: 'Nuevo encargo' })
  await form.getByRole('combobox', { name: 'Cliente' }).fill(cliente.nombre)
  await form.getByRole('option', { name: new RegExp(cliente.nombre) }).click()
  await form.getByLabel('Hora de entrega').fill('17:00')
  const item = form.getByRole('listitem', { name: 'Ítem 1' })
  await item.getByLabel('Descripción').fill(`Torta decorada E2E ${marca}`)
  await item.getByLabel('Precio c/u').fill('110000')
  await item.getByRole('button', { name: 'Agregar decoración al ítem 1' }).click()
  await form.getByRole('button', { name: 'Crear encargo' }).click()
  await expect(form).toContainText('La decoración necesita referencia y valor.')
  await item.getByLabel('Referencia de la decoración').fill('Letras doradas y topper')
  await item.getByLabel('Valor de la decoración').fill('25000')
  await expect(form).toContainText('$135.000')
  await form.getByRole('button', { name: 'Crear encargo' }).click()

  const detalle = page.getByRole('region', { name: /^Encargo n\.º/ })
  await expect(detalle).toContainText('Decoración: Letras doradas y topper')
  const deco = detalle.getByRole('region', { name: 'Decoración' })
  await deco.getByRole('button', { name: 'Registrar gasto de decoración' }).click()
  const gasto = page.getByRole('dialog', { name: 'Gasto de decoración' })
  await gasto.getByLabel('Qué se compró').fill('Fondant y topper')
  await gasto.getByLabel('Valor').fill('9000')
  // De la caja, Efectivo viene elegido.
  await expect(gasto.getByRole('radio', { name: 'Efectivo' })).toHaveAttribute('aria-checked', 'true')
  await gasto.getByRole('button', { name: 'Registrar gasto de $9.000' }).click()
  await expect(deco).toContainText('Fondant y topper')
  await expect(deco).toContainText('$16.000')

  await detalle.getByRole('button', { name: 'Pasar a producción' }).click()
  await detalle.getByRole('button', { name: 'Marcar como listo' }).click()
  await detalle.getByRole('button', { name: 'Entregar y cobrar $135.000' }).click()
  const entrega = page.getByRole('dialog', { name: 'Entregar y cobrar' })
  await entrega.getByRole('radio', { name: 'Efectivo' }).click()
  await entrega.getByRole('button', { name: 'Entregar y cobrar $135.000' }).click()
  await expect(detalle).toContainText('Entregado y cobrado.')
  await detalle.getByRole('link', { name: /^Venta n\.º/ }).click()
  const venta = page.locator('section').filter({ has: page.getByRole('heading', { level: 2, name: /^Venta n\.º/ }) })
  await expect(venta).toContainText('Decoración: Letras doradas y topper')
  await expect(venta).toContainText('$25.000')

  // Anular el gasto desde Gastos y volver a Encargos sin recargar: ya no cuenta.
  await page.getByRole('navigation').getByRole('link', { name: 'Gastos' }).click()
  await page.getByRole('row').filter({ hasText: 'Fondant y topper' }).first().click()
  await page.getByRole('button', { name: 'Anular gasto' }).click()
  await page.getByLabel('Motivo de la anulación').fill('Se registró dos veces')
  await page.getByRole('button', { name: 'Anular gasto' }).click()
  await expect(page.getByText('Gasto anulado: el dinero volvió a la caja abierta.')).toBeVisible()
  await page.getByRole('navigation').getByRole('link', { name: 'Encargos' }).click()
  await page.getByText(`Torta decorada E2E ${marca}`).first().click()
  const decoracion = page.getByRole('region', { name: 'Decoración' })
  await expect(decoracion).toContainText('−$0')
  await expect(decoracion).toContainText('$25.000')
  await expect(decoracion).not.toContainText('$16.000')
})
