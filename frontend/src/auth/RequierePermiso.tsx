import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { EncabezadoPagina, Tarjeta } from '../components/ui'
import { useSesion } from './contexto'

/**
 * Guardia de ruta: muestra la pantalla solo si el usuario tiene alguno de los permisos.
 * Es una ayuda de interfaz; el backend valida cada petición de todos modos.
 */
export function RequierePermiso({ permisos, children }: { permisos: string[]; children: ReactNode }) {
  const { puede } = useSesion()
  if (permisos.some(puede)) return children
  return (
    <>
      <EncabezadoPagina titulo="Sin acceso" />
      <Tarjeta className="px-6 py-10 text-center">
        <p className="text-cafe-medio">
          Tu rol no incluye esta sección. Si la necesitas, pídele acceso al administrador.
        </p>
        <Link to="/" className="mt-4 inline-block font-semibold text-fucsia underline underline-offset-4">
          Ir a mi inicio
        </Link>
      </Tarjeta>
    </>
  )
}
