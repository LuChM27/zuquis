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
  const post = async (ruta: string, data: unknown, metodo: 'post' | 'put' = 'post') => {
    const r = await request[metodo](`${API}${ruta}`, { headers: auth, data })
    expect(r.ok(), `${ruta}: ${await r.text()}`).toBeTruthy()
    return r.json()
  }
  const marca = Date.now()
  const jarabe = await post('/insumos', { nombre: `Jarabe ventas E2E ${marca}`, unidad_base: 'ml' })
  await post('/compras', { estado_pago: 'por_pagar', items: [{ insumo_id: jarabe.id, cantidad: '2000', costo_total: 20000 }] })
  const categoria = await post('/categorias', { nombre: `Bebidas ventas E2E ${marca}` })
  const producto = async (nombre: string, precio: number) => {
    const p = await post('/productos', { categoria_id: categoria.id, nombre: `${nombre} E2E ${marca}`, tipo: 'preparado', precio })
    await post(`/productos/${p.id}/receta`, { rendimiento: '1', items: [{ insumo_id: jarabe.id, cantidad: '20' }] }, 'put')
    return p
  }
  const soda = await producto('Soda ventas', 12000)
  const cafe = await producto('Café ventas', 3000)
  const galleta = await producto('Galleta ventas', 2500)
  const caja = await (await request.get(`${API}/caja/actual`, { headers: auth })).json()
  if (!caja.abierta) await post('/caja/abrir', { base_inicial: 100000 })
  return { soda, cafe, galleta }
}

test('ventas: regalo y quitar en el POS, ver la venta como comprobante y anularla', async ({ page, request }) => {
  const { soda, cafe, galleta } = await preparar(request)
  await ingresar(page)
  await page.goto('/vender')
  const buscar = page.getByLabel('Buscar producto')
  for (const p of [soda, cafe, galleta]) {
    await buscar.fill(p.nombre)
    await page.getByRole('button', { name: new RegExp(`^${p.nombre},`) }).click()
  }
  const venta = page.getByRole('complementary', { name: 'Venta actual' })
  await venta.getByRole('button', { name: `Quitar ${galleta.nombre} de la venta` }).click()
  await expect(venta.getByRole('listitem', { name: galleta.nombre })).toHaveCount(0)
  await venta.getByRole('button', { name: `${cafe.nombre} es regalo` }).click()
  await expect(venta.getByRole('button', { name: `${cafe.nombre} es regalo` })).toHaveAttribute('aria-pressed', 'true')
  await expect(venta.getByRole('listitem', { name: cafe.nombre })).toContainText('$0')
  await venta.getByRole('button', { name: /^Efectivo/ }).click()
  await venta.getByRole('button', { name: 'Cobrar $12.000' }).click()
  const lista = page.getByRole('dialog', { name: /^Venta n\.º/ })
  const titulo = (await lista.getByRole('heading').textContent()) ?? ''
  const numero = Number(titulo.replace(/\D/g, ''))
  await lista.getByRole('button', { name: 'Nueva venta' }).click()

  await page.getByRole('link', { name: 'Ventas' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Ventas' })).toBeVisible()
  await expect(page.getByRole('row', { name: new RegExp(soda.nombre) }).first()).toBeVisible()

  await page.getByLabel('Buscar por número').fill(String(numero))
  const detalle = page.locator('section').filter({ has: page.getByRole('heading', { level: 2, name: /^Venta n\.º/ }) })
  await expect(detalle).toContainText(`1 × ${soda.nombre}`)
  await expect(detalle).toContainText(`1 × ${cafe.nombre}`)
  await expect(detalle).toContainText('Regalo')
  await expect(detalle).toContainText('$12.000')

  await detalle.getByRole('button', { name: 'Anular venta' }).click()
  const anular = page.getByRole('dialog', { name: /^Anular la venta/ })
  await anular.getByLabel('Motivo').fill('El cliente devolvió el pedido')
  await anular.getByRole('button', { name: 'Anular venta' }).click()
  await expect(page.getByText(/anulada\.$/)).toBeVisible()
  await expect(page.getByRole('row', { name: /Anulada/ })).toBeVisible()
  await expect(detalle).toContainText('El cliente devolvió el pedido')
})
