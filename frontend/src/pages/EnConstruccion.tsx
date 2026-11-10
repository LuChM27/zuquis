import { Link, useLocation } from 'react-router'
import { EncabezadoPagina, Tarjeta, TituloTarjeta } from '../components/ui'
import { SECCIONES } from '../layout/navegacion'

export function EnConstruccion({ fase, descripcion }: { fase: number; descripcion?: string }) {
  return (
    <Tarjeta className="px-6 py-10 text-center">
      <TituloTarjeta>Esta pantalla llega en la fase {fase}</TituloTarjeta>
      {descripcion && <p className="mx-auto mt-3 max-w-[60ch] text-cafe-medio">{descripcion}</p>}
    </Tarjeta>
  )
}

/** Página provisional para las secciones que aún no se construyen. */
export function SeccionPendiente() {
  const { pathname } = useLocation()
  const seccion = SECCIONES.find((s) => s.ruta === pathname)
  return (
    <>
      <EncabezadoPagina titulo={seccion?.nombre ?? 'Sección'} />
      <EnConstruccion fase={seccion?.fase ?? 0} />
    </>
  )
}

export function NoEncontrada() {
  return (
    <>
      <EncabezadoPagina titulo="No encontramos esta página" />
      <Tarjeta className="px-6 py-10 text-center">
        <p className="text-cafe-medio">La dirección no existe o cambió.</p>
        <Link to="/" className="mt-4 inline-block font-semibold text-fucsia underline underline-offset-4">
          Volver al inicio
        </Link>
      </Tarjeta>
    </>
  )
}
