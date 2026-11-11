# Pruebas de extremo a extremo (Playwright)

Corren contra la API real. Antes de ejecutarlas:

1. `docker compose up -d db` y la API en `http://localhost:8000` (o `docker compose up`).
2. Un administrador de prueba en la base de desarrollo:
   `python -m app.cli crear-admin --email admin@zuquis.local --nombre Administrador --clave zuquis-dev-123`
   (o define `E2E_ADMIN_EMAIL` y `E2E_ADMIN_CLAVE` con otro usuario de prueba).
3. `npm run e2e`

Las pruebas crean, si no existe, el usuario `cajero.e2e@zuquis.local` para verificar permisos.
En local usan el Chrome instalado; en CI, Chromium de Playwright.
