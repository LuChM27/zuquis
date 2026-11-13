import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test'

const ADMIN = {
  email: process.env.E2E_ADMIN_EMAIL ?? 'admin@zuquis.local',
  clave: process.env.E2E_ADMIN_CLAVE ?? 'zuquis-dev-123',
}
const API = process.env.E2E_API_URL ?? 'http://localhost:8000/api/v1'

/** Elige en un Buscador: escribe parte del nombre y hace clic en la opción. */
async function elegir(zona: Page | Locator, etiqueta: string, texto: string) {
  await zona.getByRole('combobox', { name: etiqueta }).fill(texto.slice(0, 12))
  await zona.getByRole('option', { name: texto }).click()
}

async function autenticar(request: APIRequestContext) {
  const login = await request.post(`${API}/auth/login`, { data: { email: ADMIN.email, password: ADMIN.clave } })
  expect(login.ok(), 'el administrador de prueba debe existir (ver e2e/README.md)').toBeTruthy()
  return { Authorization: `Bearer ${(await login.json()).access_token}` }
}

async function ingresar(page: Page) {
  await page.goto('/ingresar')
  await page.getByLabel('Correo').fill(ADMIN.email)
  await page.getByLabel('Contraseña', { exact: true }).fill(ADMIN.clave)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page).not.toHaveURL(/\/ingresar$/)
}

async function crearInsumo(request: APIRequestContext, auth: Record<string, string>, nombre: string, presentacion: string, factor: string) {
  const r = await request.post(`${API}/insumos`, {
    headers: auth,
    data: { nombre, unidad_base: 'g', presentaciones: [{ nombre: presentacion, factor }] },
  })
  expect(r.ok()).toBeTruthy()
  return r.json()
}

test('registrar una compra de dos líneas y ver los lotes nuevos en Inventario', async ({ page, request }) => {
  const auth = await autenticar(request)
  const marca = Date.now()
  const harina = await crearInsumo(request, auth, `Harina compra E2E ${marca}`, 'Bulto 50 kg', '50000')
  const azucar = await crearInsumo(request, auth, `Azúcar compra E2E ${marca}`, 'Bolsa 2,5 kg', '2500')

  await ingresar(page)
  await page.goto('/compras?seccion=nueva')
  const linea1 = page.getByRole('listitem', { name: 'Línea 1' })
  await elegir(linea1, 'Insumo', harina.nombre)
  await linea1.getByLabel('Cantidad').fill('2')
  await linea1.getByLabel('Costo total').fill('300000')
  await expect(linea1).toContainText('= 100 kg a $3.000 el kg')

  await page.getByRole('button', { name: 'Agregar línea' }).click()
  const linea2 = page.getByRole('listitem', { name: 'Línea 2' })
  await elegir(linea2, 'Insumo', azucar.nombre)
  await linea2.getByLabel('Cantidad').fill('4')
  await linea2.getByLabel('Costo total').fill('45000')
  await expect(linea2).toContainText('= 10 kg a $4.500 el kg')
  await expect(page.getByText('$345.000')).toBeVisible()

  await page.getByRole('button', { name: 'Registrar compra' }).last().click()
  await expect(page.getByText('Compra registrada por $345.000: 2 lotes nuevos en inventario.')).toBeVisible()
  await expect(page).toHaveURL(/seccion=compras/)

  await page.goto('/inventario')
  await expect(page.getByRole('row').filter({ hasText: harina.nombre })).toContainText('100 kg')
  const filaAzucar = page.getByRole('row').filter({ hasText: azucar.nombre })
  await expect(filaAzucar).toContainText('10 kg')
  await filaAzucar.click()
  const panel = page.locator('section').filter({ has: page.getByRole('heading', { level: 2, name: azucar.nombre }) })
  await expect(panel.getByText('Compra de 10 kg a $4.500 el kg')).toBeVisible()
  await expect(panel.getByText('Se usa primero')).toBeVisible()
})

test('registrar producción con vista previa del costo', async ({ page, request }) => {
  const auth = await autenticar(request)
  const marca = Date.now()
  const harina = await crearInsumo(request, auth, `Harina prod E2E ${marca}`, 'Bolsa 1 kg', '1000')
  await request.post(`${API}/compras`, {
    headers: auth,
    data: { estado_pago: 'por_pagar', items: [{ insumo_id: harina.id, cantidad: '1000', costo_total: 3000 }] },
  })
  const categorias: { id: string }[] = await (await request.get(`${API}/categorias`, { headers: auth })).json()
  const producto = await (
    await request.post(`${API}/productos`, {
      headers: auth,
      data: { categoria_id: categorias[0].id, nombre: `Galleta E2E ${marca}`, tipo: 'lote', precio: 1500, dias_vida_util: 5 },
    })
  ).json()
  await request.put(`${API}/productos/${producto.id}/receta`, {
    headers: auth,
    data: { rendimiento: '12', items: [{ insumo_id: harina.id, cantidad: '600' }] },
  })

  await ingresar(page)
  await page.goto('/inventario')
  await page.getByRole('button', { name: 'Registrar producción' }).click()
  await expect(page).toHaveURL(/seccion=produccion/)
  await elegir(page, 'Producto', producto.nombre)
  await page.getByLabel('Unidades producidas').fill('12')

  // 600 g × $3 = $1.800 ÷ 12 = $150 por unidad.
  const previa = page.getByRole('region', { name: 'Vista previa' })
  await expect(previa).toContainText(`${harina.nombre} · 600 g`)
  await expect(previa).toContainText('$1.800')
  await expect(previa).toContainText('$150')
  await previa.getByRole('button', { name: 'Confirmar producción' }).click()
  await expect(page.getByText(`Producción registrada: 12 ${producto.nombre} a $150 c/u.`)).toBeVisible()
  await expect(page.getByRole('row').filter({ hasText: producto.nombre }).first()).toContainText('12')
})
