import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { ProveedorSesion } from './auth/sesion'
import { AppLayout } from './layout/AppLayout'
import { SECCIONES } from './layout/navegacion'
import { SeccionPendiente, NoEncontrada } from './pages/EnConstruccion'
import { Ingresar } from './pages/Ingresar'
import { Inicio } from './pages/Inicio'
import './styles.css'

const clienteQuery = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
})

const router = createBrowserRouter([
  { path: '/ingresar', element: <Ingresar /> },
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <Inicio /> },
      ...SECCIONES.filter((s) => s.ruta !== '/').map((s) => ({ path: s.ruta, element: <SeccionPendiente /> })),
      { path: '*', element: <NoEncontrada /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={clienteQuery}>
      <ProveedorSesion>
        <RouterProvider router={router} />
      </ProveedorSesion>
    </QueryClientProvider>
  </StrictMode>,
)
