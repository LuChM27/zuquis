import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const ADMIN = {
  email: process.env.E2E_ADMIN_EMAIL ?? 'admin@zuquis.local',
  clave: process.env.E2E_ADMIN_CLAVE ?? 'zuquis-dev-123',
}
const API = process.env.E2E_API_URL ?? 'http://localhost:8000/api/v1'

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

/** Carta propia de la prueba: malteada con adición de helado y soda, con receta e insumo con stock. */
async function prepararCarta(request: APIRequestContext) {
  const auth = await autenticar(request)
  const marca = Date.now()
  const post = async (ruta: string, data: unknown, metodo: 'post' | 'put' = 'post') => {
    const r = await request[metodo](`${API}${ruta}`, { headers: auth, data })
    expect(r.ok(), `${ruta}: ${await r.text()}`).toBeTruthy()
    return r.json()
  }
  const leche = await post('/insumos', { nombre: `Leche venta E2E ${marca}`, unidad_base: 'ml' })
  await post('/compras', { estado_pago: 'por_pagar', items: [{ insumo_id: leche.id, cantidad: '20000', costo_total: 60000 }] })
  const categoria = await post('/categorias', { nombre: `Malteadas E2E ${marca}`, icono: 'cup-soda' })
  const helado = await post('/modificadores', { nombre: `Helado E2E ${marca}`, precio: 5000 })
  const producto = async (nombre: string, precio: number, modificador_ids: string[] = []) => {
    const p = await post('/productos', { categoria_id: categoria.id, nombre, tipo: 'preparado', precio, modificador_ids })
    await post(`/productos/${p.id}/receta`, { rendimiento: '1', items: [{ insumo_id: leche.id, cantidad: '200' }] }, 'put')
    return p
  }
  const malteada = await producto(`Malteada E2E ${marca}`, 16000, [helado.id])
  const soda = await producto(`Soda E2E ${marca}`, 12000)

  const caja = await (await request.get(`${API}/caja/actual`, { headers: auth })).json()
  if (!caja.abierta) await post('/caja/abrir', { base_inicial: 100000 })
  return { malteada, soda, helado }
}

const tarjeta = (page: Page, nombre: string) => page.getByRole('button', { name: new RegExp(`^${nombre},`) })

test('vender: venta completa con adición, descuento, propina y pago mixto', async ({ page, request }) => {
  const { malteada, soda, helado } = await prepararCarta(request)
  await ingresar(page)
  await page.goto('/vender')

  await page.getByLabel('Buscar producto').fill(malteada.nombre)
  await tarjeta(page, malteada.nombre).click()
  await page.getByLabel('Buscar producto').fill(soda.nombre)
  await tarjeta(page, soda.nombre).click()
  await tarjeta(page, soda.nombre).click()

  const venta = page.getByRole('complementary', { name: 'Venta actual' })
  await venta.getByRole('button', { name: malteada.nombre, exact: true }).click()
  const linea = page.getByRole('dialog', { name: malteada.nombre })
  await linea.getByLabel(new RegExp(helado.nombre)).check()
  await linea.getByRole('button', { name: /^Guardar/ }).click()
  await expect(venta.getByText(`+ ${helado.nombre}`)).toBeVisible()

  await venta.getByRole('button', { name: 'Agregar descuento' }).click()
  const descuento = page.getByRole('dialog', { name: 'Descuento a la venta' })
  await descuento.getByRole('radio', { name: 'Valor ($)' }).click()
  await descuento.getByLabel('Pesos').fill('3000')
  await descuento.getByLabel('Motivo').fill('Cliente frecuente')
  await descuento.getByRole('button', { name: 'Aplicar' }).click()

  await venta.getByRole('button', { name: 'Agregar propina' }).click()
  const propina = page.getByRole('dialog', { name: 'Propina' })
  await propina.getByLabel('Valor de la propina').fill('2000')
  await propina.getByRole('button', { name: 'Aplicar' }).click()

  // 21.000 + 2 × 12.000 = 45.000 − 3.000 = 42.000 de venta + 2.000 de propina.
  await expect(venta.getByText('$42.000')).toBeVisible()
  await expect(venta.getByRole('button', { name: 'Cobrar $44.000' })).toBeDisabled()

  await venta.getByRole('button', { name: /^Efectivo/ }).click()
  await venta.getByRole('button', { name: /^Nequi/ }).click()
  await venta.getByLabel('¿Cuánto paga con Nequi?').fill('20000')
  await expect(venta.getByRole('button', { name: 'Efectivo $24.000' })).toBeVisible()
  await venta.getByLabel('Recibe en efectivo (para el cambio)').fill('30000')
  await expect(venta.getByText('Cambio: $6.000')).toBeVisible()
  await venta.getByRole('button', { name: 'Cobrar $44.000' }).click()

  const lista = page.getByRole('dialog', { name: /^Venta n\.º/ })
  await expect(lista.getByText('Cambio para entregar')).toBeVisible()
  await expect(lista.getByText('$6.000')).toBeVisible()
  await expect(lista.getByText('$44.000')).toBeVisible()
  await lista.getByRole('button', { name: 'Nueva venta' }).click()
  await expect(venta.getByText('Toca un producto para agregarlo a la venta.')).toBeVisible()
})

test('vender en celular: barra inferior y cobro en hoja completa @celular', async ({ page, request }) => {
  const { soda } = await prepararCarta(request)
  await ingresar(page)
  await page.goto('/vender')

  await page.getByLabel('Buscar producto').fill(soda.nombre)
  await tarjeta(page, soda.nombre).click()
  await tarjeta(page, soda.nombre).click()
  await expect(tarjeta(page, soda.nombre)).toHaveAccessibleName(/2 en la venta/)

  await page.getByRole('button', { name: /Ver y cobrar/ }).click()
  const hoja = page.getByRole('dialog', { name: 'Venta actual' })
  await hoja.getByRole('button', { name: /^Efectivo/ }).click()
  await hoja.getByRole('button', { name: /^Nequi/ }).click()
  await hoja.getByLabel('¿Cuánto paga con Nequi?').fill('10000')
  await hoja.getByRole('button', { name: 'Cobrar $24.000' }).click()

  const lista = page.getByRole('dialog', { name: /^Venta n\.º/ })
  await expect(lista.getByText('Nequi')).toBeVisible()
  await expect(lista.getByText('$14.000')).toBeVisible()
  await lista.getByRole('button', { name: 'Nueva venta' }).click()
})
