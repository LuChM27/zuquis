import { createContext, useContext } from 'react'
import type { YoSalida } from '../lib/api'

export type Estado = { tipo: 'cargando' } | { tipo: 'anonimo' } | { tipo: 'autenticado'; yo: YoSalida }

export interface Sesion {
  estado: Estado
  iniciar: (email: string, password: string, sedeId?: string) => Promise<void>
  cerrar: () => Promise<void>
  puede: (permiso: string) => boolean
}

export const ContextoSesion = createContext<Sesion | null>(null)

export function useSesion(): Sesion {
  const s = useContext(ContextoSesion)
  if (!s) throw new Error('useSesion debe usarse dentro de ProveedorSesion')
  return s
}

/** Atajo para pantallas que solo se muestran con sesión iniciada. */
export function useYo(): YoSalida {
  const { estado } = useSesion()
  if (estado.tipo !== 'autenticado') throw new Error('Se requiere una sesión iniciada')
  return estado.yo
}
