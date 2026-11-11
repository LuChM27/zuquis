import { expect, test, type Page } from '@playwright/test'

/** Credenciales de prueba del entorno de desarrollo / CI (nunca de producción). */
const ADMIN = {
  email: process.env.E2E_ADMIN_EMAIL ?? 'admin@zuquis.local',
  clave: process.env.E2E_ADMIN_CLAVE ?? 'zuquis-dev-123',
}
const CAJERO = { email: 'cajero.e2e@zuquis.local', clave: 'cajero-e2e-123' }
const API = process.env.E2E_API_URL ?? 'http://localhost:8000/api/v1'

async function ingresar(page: Page, email: string, clave: string) {
  await page.goto('/ingresar')
  await page.getByLabel('Correo').fill(email)
  await page.getByLabel('Contraseña', { exact: true }).fill(clave)
  await page.getByRole('button', { name: 'Entrar' }).click()
}

test.beforeAll(async ({ request }) => {
  // Crea (si no existe) un cajero para probar permisos.
  const login = await request.post(`${API}/auth/login`, { data: { email: ADMIN.email, password: ADMIN.clave } })
  expect(login.ok(), 'el administrador de prueba debe existir (ver e2e/README.md)').toBeTruthy()
  const { access_token, sede } = await login.json()
  const auth = { Authorization: `Bearer ${access_token}` }
  const roles: { id: string; nombre: string }[] = await (await request.get(`${API}/roles`, { headers: auth })).json()
  const cajero = roles.find((r) => r.nombre.startsWith('Cajero'))!
  const r = await request.post(`${API}/usuarios`, {
    headers: auth,
    data: { nombre: 'Cajero E2E', email: CAJERO.email, password: CAJERO.clave, roles: [{ rol_id: cajero.id, sede_id: sede.id }] },
  })
  expect([201, 409]).toContain(r.status())
})

test('login correcto lleva al inicio con el menú completo', async ({ page }) => {
  await ingresar(page, ADMIN.email, ADMIN.clave)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(/Buen(os|as) (días|tardes|noches)/)
  await expect(page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: 'Configuración' })).toBeVisible()
})

test('login fallido muestra el error sin entrar', async ({ page }) => {
  await ingresar(page, 'nadie@zuquis.local', 'clave-incorrecta')
  await expect(page.getByRole('alert')).toContainText('Usuario o contraseña incorrectos')
  await expect(page).toHaveURL(/\/ingresar$/)
})

test('un cajero no ve ni puede abrir rutas restringidas', async ({ page }) => {
  await ingresar(page, CAJERO.email, CAJERO.clave)
  await expect(page).toHaveURL(/\/vender$/)
  const menu = page.getByRole('navigation', { name: 'Principal' })
  await expect(menu.getByRole('link', { name: 'Vender' })).toBeVisible()
  await expect(menu.getByRole('link', { name: 'Configuración' })).toHaveCount(0)
  await expect(menu.getByRole('link', { name: 'Inventario' })).toHaveCount(0)

  for (const ruta of ['/configuracion', '/inventario', '/compras']) {
    await page.goto(ruta)
    await expect(page.getByRole('heading', { name: 'Sin acceso' })).toBeVisible()
  }
})

test('recargar conserva la sesión; sin la cookie de renovación vuelve al login', async ({ page, context }) => {
  await ingresar(page, ADMIN.email, ADMIN.clave)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await page.reload()
  await expect(page).not.toHaveURL(/\/ingresar/)
  await expect(page.getByRole('navigation', { name: 'Principal' })).toBeVisible()

  await context.clearCookies()
  await page.reload()
  await expect(page).toHaveURL(/\/ingresar$/)
})

test('a 360 px no hay scroll horizontal', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 })
  await page.goto('/ingresar')
  const sinDesborde = () =>
    page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)
  expect(await sinDesborde()).toBe(true)

  await ingresar(page, ADMIN.email, ADMIN.clave)
  for (const ruta of ['/', '/configuracion', '/configuracion?seccion=roles', '/configuracion?seccion=negocio']) {
    await page.goto(ruta)
    await expect(page.getByRole('button', { name: 'Abrir menú' })).toBeVisible()
    expect(await sinDesborde(), `desborde horizontal en ${ruta}`).toBe(true)
  }
})
