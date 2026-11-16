import { defineConfig, devices } from '@playwright/test'

/**
 * Pruebas de extremo a extremo contra la API real. Requieren la API en :8000 con un
 * administrador creado (ver e2e/README.md). Usan el Chrome instalado en el equipo o runner.
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
    // Sin capturas en la traza: con Chrome 157 la grabación de pantalla deja los campos sin poder
    // llenarse. Las instantáneas del DOM siguen sirviendo para revisar un fallo.
    trace: { mode: 'retain-on-failure', screenshots: false },
    locale: 'es-CO',
    timezoneId: 'America/Bogota',
  },
  projects: [
    // Usa el Chrome instalado (los runners de GitHub ya lo traen): no hay que descargar navegadores.
    { name: 'escritorio', use: { ...devices['Desktop Chrome'], channel: 'chrome' }, grepInvert: /@celular/ },
    // Las pruebas marcadas con @celular corren a tamaño de teléfono (Pixel 7, 412 px).
    {
      name: 'celular',
      use: { ...devices['Pixel 7'], channel: 'chrome' },
      grep: /@celular/,
    },
  ],
  webServer: {
    command: 'npm run build && npx vite preview --port 4173 --strictPort',
    url: 'http://localhost:4173',
    reuseExistingServer: !enCI,
    timeout: 120_000,
  },
})
