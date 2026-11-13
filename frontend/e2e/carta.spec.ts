import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test'

const ADMIN = {
  email: process.env.E2E_ADMIN_EMAIL ?? 'admin@zuquis.local',
  clave: process.env.E2E_ADMIN_CLAVE ?? 'zuquis-dev-123',
}
const PRODUCCION = { email: 'produccion.e2e@zuquis.local', clave: 'produccion-e2e-123' }
const API = process.env.E2E_API_URL ?? 'http://localhost:8000/api/v1'

/** Elige en un Buscador: escribe parte del nombre y hace clic en la opción. */
async function elegir(zona: Page | Locator, etiqueta: string, texto: string) {
  await zona.getByRole('combobox', { name: etiqueta }).fill(texto.slice(0, 12))
  await zona.getByRole('option', { name: texto }).click()
}

async function autenticar(request: APIRequestContext) {
  const login = await request.post(`${API}/auth/login`, { data: { email: ADMIN.email, password: ADMIN.clave } })
  expect(login.ok(), 'el administrador de prueba debe existir (ver e2e/README.md)').toBeTruthy()
  const { access_token, sede } = await login.json()
  return { auth: { Authorization: `Bearer ${access_token}` }, sede }
}

async function ingresar(page: Page, email: string, clave: string) {
  await page.goto('/ingresar')
  await page.getByLabel('Correo').fill(email)
  await page.getByLabel('Contraseña', { exact: true }).fill(clave)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page).not.toHaveURL(/\/ingresar$/)
}

test('carta: crear un producto con su receta y ver el costo teórico', async ({ page, request }) => {
  const { auth } = await autenticar(request)
  const marca = Date.now()
  // Un insumo con una compra para que el costo teórico esté completo: 1000 g a $8.000 → $8/g.
  const insumo = await (
    await request.post(`${API}/insumos`, { headers: auth, data: { nombre: `Queso E2E ${marca}`, unidad_base: 'g' } })
  ).json()
  await request.post(`${API}/compras`, {
    headers: auth,
    data: { estado_pago: 'por_pagar', items: [{ insumo_id: insumo.id, cantidad: '1000', costo_total: 8000 }] },
  })

  await ingresar(page, ADMIN.email, ADMIN.clave)
  await page.goto('/carta')
  await page.getByRole('button', { name: 'Nuevo producto' }).click()
  const panel = page.locator('section').filter({ has: page.getByRole('heading', { level: 2, name: 'Nuevo producto' }) })
  const nombre = `Pandebono E2E ${marca}`
  await panel.getByLabel('Nombre').fill(nombre)
  await panel.getByLabel('Producido por lote').check()
  await panel.getByLabel('Precio de venta').fill('3000')
  await panel.getByRole('button', { name: 'Crear producto' }).click()

  const detalle = page.locator('section').filter({ has: page.getByRole('heading', { level: 2, name: nombre }) })
  await expect(detalle).toBeVisible()
  await detalle.getByRole('tab', { name: 'Receta' }).click()
  await detalle.getByLabel('Rinde (unidades)').fill('10')
  await elegir(detalle, 'Insumo', insumo.nombre)
  await detalle.getByLabel('Cantidad en g').fill('1500')
  await detalle.getByRole('button', { name: 'Guardar receta' }).click()
  await expect(page.getByText('Receta guardada: versión 1.')).toBeVisible()

  // 1500 g × $8 = $12.000 ÷ 10 = $1.200 por unidad; margen $1.800 sobre $3.000 (60 %).
  const costo = detalle.getByRole('region', { name: 'Costo y margen' })
  await expect(costo).toContainText('$12.000')
  await expect(costo).toContainText('$1.200')
  await expect(costo).toContainText('$1.800 · 60 %')
})

test('producción ve las recetas pero no puede editar precios', async ({ page, request }) => {
  const { auth, sede } = await autenticar(request)
  const roles: { id: string; nombre: string }[] = await (await request.get(`${API}/roles`, { headers: auth })).json()
  const rol = roles.find((r) => r.nombre.startsWith('Producción'))!
  const r = await request.post(`${API}/usuarios`, {
    headers: auth,
    data: { nombre: 'Producción E2E', email: PRODUCCION.email, password: PRODUCCION.clave, roles: [{ rol_id: rol.id, sede_id: sede.id }] },
  })
  expect([201, 409]).toContain(r.status())
  // Un producto con receta para que haya algo que ver.
  const categorias: { id: string }[] = await (await request.get(`${API}/categorias`, { headers: auth })).json()
  const producto = await (
    await request.post(`${API}/productos`, {
      headers: auth,
      data: { categoria_id: categorias[0].id, nombre: `Brownie E2E ${Date.now()}`, tipo: 'lote', precio: 5000 },
    })
  ).json()
  const insumos: { id: string }[] = await (await request.get(`${API}/insumos`, { headers: auth })).json()
  await request.put(`${API}/productos/${producto.id}/receta`, {
    headers: auth,
    data: { rendimiento: '1', items: [{ insumo_id: insumos[0].id, cantidad: '10' }] },
  })

  await ingresar(page, PRODUCCION.email, PRODUCCION.clave)
  await page.goto('/carta')
  await expect(page.getByRole('tab', { name: 'Categorías' })).toHaveCount(0)
  await page.getByRole('row').filter({ hasText: producto.nombre }).click()
  const detalle = page.locator('section').filter({ has: page.getByRole('heading', { level: 2, name: producto.nombre }) })
  await expect(detalle.getByRole('button', { name: 'Guardar nueva versión' })).toBeEnabled()
  await expect(detalle.getByRole('tab', { name: 'Precios' })).toHaveCount(0)
  await detalle.getByRole('tab', { name: 'Datos' }).click()
  await expect(detalle.getByLabel('Precio de venta')).toHaveCount(0)
  await expect(detalle.getByText('Los datos y el precio los cambia el administrador.')).toBeVisible()
})
