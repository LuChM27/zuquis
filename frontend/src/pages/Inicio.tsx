import { Navigate } from 'react-router'
import { useSesion, useYo } from '../auth/contexto'
import { seccionesVisibles } from '../layout/navegacion'
import { Dashboard } from './inicio/Dashboard'

/** Inicio: el dashboard del día (mockup docs/mockups/dashboard.png). */
export function Inicio() {
  const yo = useYo()
  const { puede } = useSesion()

  // Quien no ve el dashboard (cajero, producción) entra directo a su primera sección.
  if (!puede('reportes.ver')) {
    const primera = seccionesVisibles(yo.permisos)[0]
    if (primera && primera.ruta !== '/') return <Navigate to={primera.ruta} replace />
  }

  return <Dashboard />
}
