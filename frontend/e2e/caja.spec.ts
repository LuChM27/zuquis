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

/** Un producto vendible propio de la prueba y la caja cerrada para empezar el turno desde cero. */
async function preparar(request: APIRequestContext) {
  const login = await request.post(`${API}/auth/login`, { data: { email: ADMIN.email, password: ADMIN.clave } })
  expect(login.ok(), 'el administrador de prueba debe existir (ver e2e/README.md)').toBeTruthy()
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` }
  const post = async (ruta: string, data: unknown, metodo: 'post' | 'put' = 'post') => {
    const r = await request[metodo](`${API}${ruta}`, { headers: auth, data })
    expect(r.ok(), `${ruta}: ${await r.text()}`).toBeTruthy()
    return r.json()
  }
  const marca = Date.now()
  const leche = await post('/insumos', { nombre: `Leche caja E2E ${marca}`, unidad_base: 'ml' })
  await post('/compras', { estado_pago: 'por_pagar', items: [{ insumo_id: leche.id, cantidad: '5000', costo_total: 15000 }] })
  const categoria = await post('/categorias', { nombre: `Bebidas caja E2E ${marca}` })
  const soda = await post('/productos', { categoria_id: categoria.id, nombre: `Soda caja E2E ${marca}`, tipo: 'preparado', precio: 12000 })
  await post(`/productos/${soda.id}/receta`, { rendimiento: '1', items: [{ insumo_id: leche.id, cantidad: '200' }] }, 'put')

  // Si quedó una caja abierta de otra prueba, se cierra cuadrada.
  const caja = await (await request.get(`${API}/caja/actual`, { headers: auth })).json()
  if (caja.abierta) {
    const contado = caja.esperado.map((e: { metodo_pago_id: string; esperado: number }) => ({
      metodo_pago_id: e.metodo_pago_id,
      contado: e.esperado,
    }))
    await post('/caja/cerrar', { contado })
  }
  return { soda, marca }
}

test('caja: abrir, vender, registrar un gasto y cerrar con diferencia y observación', async ({ page, request }) => {
  const { soda, marca } = await preparar(request)
  await ingresar(page)

  // 1. Abrir la caja con $100.000 de base.
  await page.goto('/caja')
  await page.getByLabel('Base inicial en efectivo').fill('100000')
  await page.getByRole('button', { name: 'Abrir caja' }).click()
  await expect(page.getByText(/Caja abierta desde/)).toBeVisible()

  // 2. Vender una soda en efectivo.
  await page.goto('/vender')
  await page.getByLabel('Buscar producto').fill(soda.nombre)
  await page.getByRole('button', { name: new RegExp(`^${soda.nombre},`) }).click()
  const venta = page.getByRole('complementary', { name: 'Venta actual' })
  await venta.getByRole('button', { name: /^Efectivo/ }).click()
  await venta.getByRole('button', { name: 'Cobrar $12.000' }).click()
  await page.getByRole('dialog', { name: /^Venta n\.º/ }).getByRole('button', { name: 'Nueva venta' }).click()

  // 3. Un gasto de $8.000 pagado de la caja.
  await page.goto('/gastos')
  await page.getByRole('button', { name: 'Registrar gasto' }).first().click()
  const form = page.locator('section').filter({ has: page.getByRole('heading', { level: 2, name: 'Registrar gasto' }) })
  await form.getByRole('combobox', { name: 'Categoría' }).fill('Papeler')
  await form.getByRole('option', { name: /Papelería/ }).click()
  await form.getByLabel('Descripción').fill(`Resma de papel E2E ${marca}`)
  await form.getByLabel('Valor').fill('8000')
  await form.getByRole('button', { name: 'Registrar gasto' }).click()
  await expect(page.getByText('Gasto de $8.000 registrado.')).toBeVisible()

  // 4. Cierre: debería haber 100.000 + 12.000 − 8.000 = $104.000 en efectivo; se cuentan $103.500.
  await page.goto('/caja?seccion=cierre')
  await expect(page.getByRole('heading', { name: 'Cierre de caja' })).toBeVisible()
  const efectivo = page.getByRole('row', { name: /^Efectivo/ })
  await expect(efectivo).toContainText('$104.000')
  await page.getByLabel('Contado en Efectivo').fill('103500')
  await expect(efectivo).toContainText('−$500')
  await expect(page.getByText('Gastos pagados de la caja').first()).toBeVisible()

  await page.getByRole('button', { name: 'Confirmar y cerrar caja' }).click()
  await expect(page.getByText('Hay diferencias entre lo contado y lo esperado: escribe una observación.')).toBeVisible()
  await page.getByLabel('Observación (obligatoria si hay diferencia)').fill('Faltan $500, posiblemente cambio mal entregado.')
  await page.getByRole('button', { name: 'Confirmar y cerrar caja' }).click()

  const cerrada = page.getByRole('dialog', { name: 'Caja cerrada' })
  await expect(cerrada).toContainText('−$500')
  await cerrada.getByRole('button', { name: 'Ver historial' }).click()
  await expect(page.getByText('Observación:')).toBeVisible()
  await expect(page.getByText('Faltan $500, posiblemente cambio mal entregado.')).toBeVisible()
  await expect(page.getByText(/Caja cerrada$/).first()).toBeVisible()
})
