import { Navigate } from 'react-router'
import { useSesion, useYo } from '../auth/contexto'
import { EncabezadoPagina } from '../components/ui'
import { seccionesVisibles } from '../layout/navegacion'
import { fechaConDia, saludo } from '../lib/formato'
import { EnConstruccion } from './EnConstruccion'

/** Dashboard (mockup docs/mockups/dashboard.png). Las cifras llegan en la fase 4. */
export function Inicio() {
  const yo = useYo()
  const { puede } = useSesion()

  // Quien no ve el dashboard (cajero, producción) entra directo a su primera sección.
  if (!puede('reportes.ver')) {
    const primera = seccionesVisibles(yo.permisos)[0]
    if (primera && primera.ruta !== '/') return <Navigate to={primera.ruta} replace />
  }

  const ahora = new Date()
  return (
    <>
      <EncabezadoPagina contexto={`${fechaConDia(ahora)} · ${yo.sede.nombre}`} titulo={saludo(ahora)} />
      <EnConstruccion fase={4} descripcion="Aquí verás las ventas, gastos y ganancia del día, cómo pagaron, lo más vendido, los encargos para hoy y las alertas de inventario." />
    </>
  )
}
