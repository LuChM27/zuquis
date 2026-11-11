import { defineConfig, devices } from '@playwright/test'

/**
 * Pruebas de extremo a extremo contra la API real. Requieren la API en :8000 con un
 * administrador creado (ver e2e/README.md). En local usan el Chrome instalado; en CI, Chromium.
 */
const enCI = !!process.env.CI

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: enCI ? 1 : 0,
  reporter: enCI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://localhost:4173',
    trace: 'retain-on-failure',
    locale: 'es-CO',
    timezoneId: 'America/Bogota',
  },
  projects: [
    { name: 'escritorio', use: { ...devices['Desktop Chrome'], channel: enCI ? undefined : 'chrome' } },
  ],
  webServer: {
    command: 'npm run build && npx vite preview --port 4173 --strictPort',
    url: 'http://localhost:4173',
    reuseExistingServer: !enCI,
    timeout: 120_000,
  },
})
