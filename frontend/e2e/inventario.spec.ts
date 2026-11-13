import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const ADMIN = {
  email: process.env.E2E_ADMIN_EMAIL ?? 'admin@zuquis.local',
  clave: process.env.E2E_ADMIN_CLAVE ?? 'zuquis-dev-123',
}
const API = process.env.E2E_API_URL ?? 'http://localhost:8000/api/v1'

/** Crea por la API un insumo con dos compras a precios distintos; devuelve su nombre. */
async function insumoConDosLotes(request: APIRequestContext): Promise<string> {
  const login = await request.post(`${API}/auth/login`, { data: { email: ADMIN.email, password: ADMIN.clave } })
  expect(login.ok(), 'el administrador de prueba debe existir (ver e2e/README.md)').toBeTruthy()
  const auth = { Authorization: `Bearer ${(await login.json()).access_token}` }
  const nombre = `Harina E2E ${Date.now()}`
  const insumo = await (
    await request.post(`${API}/insumos`, {
      headers: auth,
      data: { nombre, unidad_base: 'g', stock_minimo: '5000', presentaciones: [{ nombre: 'Bulto 10 kg', factor: '10000' }] },
    })
  ).json()
  for (const costo of [30000, 40000]) {
    const r = await request.post(`${API}/compras`, {
      headers: auth,
      data: {
        estado_pago: 'por_pagar',
        items: [{ insumo_id: insumo.id, presentacion_id: insumo.presentaciones[0].id, cantidad: '1', costo_total: costo }],
      },
    })
    expect(r.ok()).toBeTruthy()
  }
  return nombre
}

async function ingresarAInventario(page: Page) {
  await page.goto('/ingresar')
  await page.getByLabel('Correo').fill(ADMIN.email)
  await page.getByLabel('Contraseña', { exact: true }).fill(ADMIN.clave)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page).not.toHaveURL(/\/ingresar$/)
  await page.goto('/inventario')
}

test('inventario: detalle PEPS, merma y kardex', async ({ page, request }) => {
  const nombre = await insumoConDosLotes(request)
  await ingresarAInventario(page)
  await expect(page.getByRole('heading', { level: 1, name: 'Inventario' })).toBeVisible()
  await expect(page.getByText('Valor del inventario')).toBeVisible()

  const fila = page.getByRole('row').filter({ hasText: nombre })
  await expect(fila).toContainText('20 kg')
  await fila.click()
  const panel = page.locator('section').filter({ has: page.getByRole('heading', { level: 2, name: nombre }) })
  await expect(panel.getByText('Se usa primero')).toBeVisible()
  await expect(panel.getByText('Siguiente')).toBeVisible()
  await expect(panel.getByText('Compra de 10 kg a $3.000 el kg')).toBeVisible()

  await panel.getByRole('button', { name: 'Registrar merma' }).click()
  const dialogo = page.getByRole('dialog', { name: 'Registrar merma' })
  await dialogo.getByLabel('Cantidad (g)').fill('2500')
  await expect(dialogo.getByText('= 2,5 kg')).toBeVisible()
  await dialogo.getByRole('button', { name: 'Registrar merma' }).click()
  await expect(page.getByText(`Merma registrada: 2,5 kg de ${nombre} (−$7.500).`)).toBeVisible()
  await expect(fila).toContainText('17,5 kg')
  await expect(panel.getByText('Quedan 7,5 kg')).toBeVisible()

  await panel.getByRole('button', { name: 'Ver kardex' }).click()
  const kardex = page.getByRole('dialog', { name: nombre })
  await expect(kardex.getByRole('row')).toHaveCount(4) // encabezado + 2 compras + merma
  await expect(kardex.getByRole('row').last()).toContainText('Merma')
  await expect(kardex.getByRole('row').last()).toContainText('$62.500')
})

test('inventario en celular: tarjetas y detalle en hoja inferior @celular', async ({ page, request }) => {
  const nombre = await insumoConDosLotes(request)
  await ingresarAInventario(page)
  await expect(page.getByRole('table')).toHaveCount(0)
  const tarjeta = page.getByRole('button', { name: new RegExp(nombre) })
  await expect(tarjeta).toContainText('Hay 20 kg · mínimo 5 kg')
  await tarjeta.click()
  const hoja = page.getByRole('dialog', { name: nombre })
  await expect(hoja.getByText('Se usa primero')).toBeVisible()
  await expect(hoja.getByText('20 kg en 2 lotes · se gasta primero el lote más antiguo')).toBeVisible()
  await hoja.getByRole('button', { name: 'Cerrar' }).click()
  await expect(hoja).toBeHidden()
})
