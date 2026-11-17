import { expect, test, type Page } from '@playwright/test'

const ADMIN = {
  email: process.env.E2E_ADMIN_EMAIL ?? 'admin@zuquis.local',
  clave: process.env.E2E_ADMIN_CLAVE ?? 'zuquis-dev-123',
}

async function ingresar(page: Page) {
  await page.goto('/ingresar')
  await page.getByLabel('Correo').fill(ADMIN.email)
  await page.getByLabel('Contraseña', { exact: true }).fill(ADMIN.clave)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page).not.toHaveURL(/\/ingresar$/)
}

async function verGaleriaYExportar(page: Page) {
  await ingresar(page)
  await page.goto('/reportes')
  await expect(page.getByRole('heading', { name: 'Reportes' })).toBeVisible()
  await page.getByRole('tab', { name: 'Semana' }).click()
  await expect(page.getByRole('heading', { name: '¿Estamos ganando?' })).toBeVisible()
  await expect(page.getByText('Cascada de utilidad')).toBeVisible()

  await page.getByRole('tab', { name: 'Tablas' }).click()
  await page.getByRole('combobox', { name: 'Reporte' }).selectOption('ventas')
  await expect(page.getByRole('heading', { name: 'Resumen' })).toBeVisible()
  const descarga = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Exportar a Excel' }).click()
  expect((await descarga).suggestedFilename()).toMatch(/^zuquis-ventas-.*\.xlsx$/)
}

test('reportes: galería de gráficos y exportar a Excel', async ({ page }) => {
  await verGaleriaYExportar(page)
})

test('reportes en el celular @celular', async ({ page }) => {
  await verGaleriaYExportar(page)
  // Sin desplazamiento horizontal de la página a 412 px.
  const ancho = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(ancho).toBeLessThanOrEqual(0)
})

test('el inicio muestra el dashboard del día', async ({ page }) => {
  await ingresar(page)
  await page.goto('/')
  await expect(page.getByText('Ventas del día')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Ir a inventario' })).toBeVisible()
})
