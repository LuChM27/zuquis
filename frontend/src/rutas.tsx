import type { ReactNode } from 'react'
import type { RouteObject } from 'react-router'
import { RequierePermiso } from './auth/RequierePermiso'
import { AppLayout } from './layout/AppLayout'
import { SECCIONES } from './layout/navegacion'
import { Configuracion } from './pages/configuracion/Configuracion'
import { NoEncontrada, SeccionPendiente } from './pages/EnConstruccion'
import { Ingresar } from './pages/Ingresar'
import { Inventario } from './pages/inventario/Inventario'
import { Inicio } from './pages/Inicio'

/** Pantallas ya construidas; el resto de secciones muestran "llega en la fase N". */
const PANTALLAS: Record<string, ReactNode> = {
  '/configuracion': <Configuracion />,
  '/inventario': <Inventario />,
}

export const rutas: RouteObject[] = [
  { path: '/ingresar', element: <Ingresar /> },
  {
    element: <AppLayout />,
    children: [
      // Inicio decide por sí mismo: sin el dashboard, lleva a la primera sección permitida.
      { index: true, element: <Inicio /> },
      ...SECCIONES.filter((s) => s.ruta !== '/').map((s) => ({
        path: s.ruta,
        element: (
          <RequierePermiso permisos={s.permisos}>{PANTALLAS[s.ruta] ?? <SeccionPendiente />}</RequierePermiso>
        ),
      })),
      { path: '*', element: <NoEncontrada /> },
    ],
  },
]
