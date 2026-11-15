import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

/**
 * Caso de control de la Fase 2, reducido (#38; el completo está en
 * backend/tests/control/fase2.md): base $50.000, una venta con pago mixto y propina, otra con
 * descuento, un gasto de caja y un cierre que cuadra al peso.
 *
 *   Venta 1: 2 sodas $24.000 + propina $2.000 → Nequi $10.000 + Efectivo $16.000
 *   Venta 2: 1 soda $12.000 − $2.000 de descuento = $10.000 en efectivo
 *   Gasto:   $5.000 de la caja
 *   Efectivo esperado = 50.000 + 16.000 + 10.000 − 5.000 = $71.000 · Nequi $10.000
 */
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
  const post = async (ruta: string, data: unknown, metodo: 'post' | 'put' = 'post') => {
    const r = await request[metodo](`${API}${ruta}`, { headers: auth, data })
    expect(r.ok(), `${ruta}: ${await r.text()}`).toBeTruthy()
    return r.json()
  }
  const marca = Date.now()
  const jarabe = await post('/insumos', { nombre: `Jarabe control E2E ${marca}`, unidad_base: 'ml' })
  await post('/compras', { estado_pago: 'por_pagar', items: [{ insumo_id: jarabe.id, cantidad: '1000', costo_total: 30000 }] })
  const categoria = await post('/categorias', { nombre: `Sodas control E2E ${marca}` })
  const soda = await post('/productos', { categoria_id: categoria.id, nombre: `Soda control E2E ${marca}`, tipo: 'preparado', precio: 12000 })
  await post(`/productos/${soda.id}/receta`, { rendimiento: '1', items: [{ insumo_id: jarabe.id, cantidad: '50' }] }, 'put')

  const caja = await (await request.get(`${API}/caja/actual`, { headers: auth })).json()
  if (caja.abierta) {
    const contado = caja.esperado.map((e: { metodo_pago_id: string; esperado: number }) => ({ metodo_pago_id: e.metodo_pago_id, contado: e.esperado }))
    await post('/caja/cerrar', { contado })
  }
  return { soda, marca }
}

test('control del día: dos ventas, un gasto y un cierre que cuadra al peso', async ({ page, request }) => {
  const { soda, marca } = await preparar(request)
  await ingresar(page)

  await page.goto('/caja')
  await page.getByLabel('Base inicial en efectivo').fill('50000')
  await page.getByRole('button', { name: 'Abrir caja' }).click()
  await expect(page.getByText(/Caja abierta desde/)).toBeVisible()

  await page.goto('/vender')
  const venta = page.getByRole('complementary', { name: 'Venta actual' })
  const tarjeta = page.getByRole('button', { name: new RegExp(`^${soda.nombre},`) })
  const terminar = async () => page.getByRole('dialog', { name: /^Venta n\.º/ }).getByRole('button', { name: 'Nueva venta' }).click()
  await page.getByLabel('Buscar producto').fill(soda.nombre)

  // Venta 1: pago mixto con propina.
  await tarjeta.click()
  await tarjeta.click()
  await venta.getByRole('button', { name: 'Agregar propina' }).click()
  await page.getByRole('dialog', { name: 'Propina' }).getByLabel('Valor de la propina').fill('2000')
  await page.getByRole('dialog', { name: 'Propina' }).getByRole('button', { name: 'Aplicar' }).click()
  await venta.getByRole('button', { name: /^Efectivo/ }).click()
  await venta.getByRole('button', { name: /^Nequi/ }).click()
  await venta.getByLabel('¿Cuánto paga con Nequi?').fill('10000')
  await expect(venta.getByRole('button', { name: 'Efectivo $16.000' })).toBeVisible()
  await venta.getByRole('button', { name: 'Cobrar $26.000' }).click()
  await terminar()

  // Venta 2: descuento de $2.000.
  await tarjeta.click()
  await venta.getByRole('button', { name: 'Agregar descuento' }).click()
  const descuento = page.getByRole('dialog', { name: 'Descuento a la venta' })
  await descuento.getByRole('radio', { name: 'Valor ($)' }).click()
  await descuento.getByLabel('Pesos').fill('2000')
  await descuento.getByLabel('Motivo').fill('Cliente frecuente')
  await descuento.getByRole('button', { name: 'Aplicar' }).click()
  await venta.getByRole('button', { name: /^Efectivo/ }).click()
  await venta.getByRole('button', { name: 'Cobrar $10.000' }).click()
  await terminar()

  // Gasto de caja.
  await page.goto('/gastos?gasto=nuevo')
  const form = page.locator('section').filter({ has: page.getByRole('heading', { level: 2, name: 'Registrar gasto' }) })
  await form.getByRole('combobox', { name: 'Categoría' }).fill('Papeler')
  await form.getByRole('option', { name: /Papelería/ }).click()
  await form.getByLabel('Descripción').fill(`Bolsas control E2E ${marca}`)
  await form.getByLabel('Valor').fill('5000')
  await form.getByRole('button', { name: 'Registrar gasto' }).click()
  await expect(page.getByText('Gasto de $5.000 registrado.')).toBeVisible()

  // Cierre: todo cuadra.
  await page.goto('/caja?seccion=cierre')
  await expect(page.getByRole('row', { name: /^Efectivo/ })).toContainText('$71.000')
  await expect(page.getByRole('row', { name: /^Nequi/ })).toContainText('$10.000')
  await page.getByLabel('Contado en Efectivo').fill('71000')
  await page.getByLabel('Contado en Nequi').fill('10000')
  await expect(page.getByRole('row', { name: /^Efectivo/ })).toContainText('$0')
  await page.getByRole('button', { name: 'Confirmar y cerrar caja' }).click()
  await expect(page.getByRole('dialog', { name: 'Caja cerrada' })).toContainText('Lo contado coincide con lo esperado.')
})
