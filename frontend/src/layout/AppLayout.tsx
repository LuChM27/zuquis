import { Navigate, Outlet } from 'react-router'
import { useSesion } from '../auth/contexto'
import { BarraLateral } from './BarraLateral'
import { CabeceraMovil } from './CabeceraMovil'

export function AppLayout() {
  const { estado } = useSesion()
  if (estado.tipo === 'cargando') return <Cargando />
  if (estado.tipo === 'anonimo') return <Navigate to="/ingresar" replace />

  return (
    <div className="flex min-h-dvh">
      <BarraLateral />
      <div className="min-w-0 flex-1">
        <CabeceraMovil />
        <main className="mx-auto max-w-[1240px] px-4 pt-6 pb-10 lg:px-11 lg:pt-10">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export function Cargando() {
  return (
    <div className="grid min-h-dvh place-items-center">
      <img src="/logo.png" alt="Cargando" className="size-20 animate-pulse rounded-full" />
    </div>
  )
}
