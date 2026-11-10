import { LogOut } from 'lucide-react'
import { NavLink } from 'react-router'
import { useSesion, useYo } from '../auth/contexto'
import { Marca } from './Marca'
import { seccionesVisibles } from './navegacion'

export function NavegacionPrincipal({ alElegir }: { alElegir?: () => void }) {
  const yo = useYo()
  return (
    <nav aria-label="Principal">
      <ul className="flex flex-col gap-1.5">
        {seccionesVisibles(yo.permisos).map(({ ruta, nombre, icono: Icono }) => (
          <li key={ruta}>
            <NavLink
              to={ruta}
              end={ruta === '/'}
              onClick={alElegir}
              className={({ isActive }) =>
                [
                  'flex h-[42px] items-center gap-3 rounded-control border px-3.5 text-base transition-colors',
                  isActive
                    ? 'border-dorado-borde bg-crema font-medium'
                    : 'border-transparent hover:bg-crema/50',
                ].join(' ')
              }
            >
              <Icono aria-hidden className="size-5 shrink-0" strokeWidth={1.6} />
              {nombre}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

/** Tarjeta inferior de la barra lateral. En la fase 2 muestra además el estado de la caja. */
export function TarjetaUsuario() {
  const yo = useYo()
  const { cerrar } = useSesion()
  return (
    <div className="flex items-start justify-between gap-2 rounded-[14px] bg-rosa-suave p-4">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold">{yo.usuario.nombre}</p>
        <p className="mt-1 truncate text-sm text-cafe-medio">
          {yo.roles[0] ?? 'Sin rol'}
          {yo.sedes.length > 1 && ` · ${yo.sede.nombre}`}
        </p>
      </div>
      <button
        type="button"
        onClick={() => void cerrar()}
        title="Cerrar sesión"
        aria-label="Cerrar sesión"
        className="-m-1.5 grid size-9 shrink-0 place-items-center rounded-control text-cafe-medio hover:bg-crema hover:text-cafe"
      >
        <LogOut aria-hidden className="size-[18px]" strokeWidth={1.6} />
      </button>
    </div>
  )
}

export function BarraLateral() {
  return (
    <aside className="sticky top-0 hidden h-dvh w-[232px] shrink-0 flex-col bg-rosa px-[19px] pt-[27px] pb-[19px] lg:flex">
      <Marca />
      <div className="mt-[23px] min-h-0 flex-1 overflow-y-auto">
        <NavegacionPrincipal />
      </div>
      <TarjetaUsuario />
    </aside>
  )
}
