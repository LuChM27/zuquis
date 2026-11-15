import type { ReactNode } from 'react'
import type { RouteObject } from 'react-router'
import { RequierePermiso } from './auth/RequierePermiso'
import { AppLayout } from './layout/AppLayout'
import { SECCIONES } from './layout/navegacion'
import { Caja } from './pages/caja/Caja'
import { Carta } from './pages/carta/Carta'
import { Compras } from './pages/compras/Compras'
import { Configuracion } from './pages/configuracion/Configuracion'
import { Gastos } from './pages/gastos/Gastos'
import { NoEncontrada, SeccionPendiente } from './pages/EnConstruccion'
import { Ingresar } from './pages/Ingresar'
import { Inventario } from './pages/inventario/Inventario'
import { Inicio } from './pages/Inicio'
import { Vender } from './pages/vender/Vender'
import { Ventas } from './pages/ventas/Ventas'

/** Pantallas ya construidas; el resto de secciones muestran "llega en la fase N". */
const PANTALLAS: Record<string, ReactNode> = {
  '/configuracion': <Configuracion />,
  '/inventario': <Inventario />,
  '/carta': <Carta />,
  '/compras': <Compras />,
  '/vender': <Vender />,
  '/ventas': <Ventas />,
  '/caja': <Caja />,
  '/gastos': <Gastos />,
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
