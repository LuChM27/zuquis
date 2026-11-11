import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { ProveedorSesion } from './auth/sesion'
import { ProveedorAvisos } from './components/avisos'
import { rutas } from './rutas'
import './styles.css'

const clienteQuery = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
})

const router = createBrowserRouter(rutas)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={clienteQuery}>
      <ProveedorSesion>
        <ProveedorAvisos>
          <RouterProvider router={router} />
        </ProveedorAvisos>
      </ProveedorSesion>
    </QueryClientProvider>
  </StrictMode>,
)
