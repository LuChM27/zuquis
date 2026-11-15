import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { alExpirarSesion, api, fijarToken, renovarSesion, type TokenSalida, type YoSalida } from '../lib/api'
import { ContextoSesion, type Estado } from './contexto'

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>({ tipo: 'cargando' })
  const clienteQuery = useQueryClient()

  const cargarYo = useCallback(async () => {
    const yo = await api<YoSalida>('/auth/me')
    setEstado({ tipo: 'autenticado', yo })
  }, [])

  useEffect(() => {
    alExpirarSesion(() => {
      clienteQuery.clear()
      setEstado({ tipo: 'anonimo' })
    })
    // Al abrir la app se intenta recuperar la sesión con la cookie de renovación.
    renovarSesion()
      .then(cargarYo)
      .catch(() => setEstado({ tipo: 'anonimo' }))
  }, [cargarYo, clienteQuery])

  const iniciar = useCallback(
    async (email: string, password: string, sedeId?: string) => {
      const datos = await api<TokenSalida>('/auth/login', {
        method: 'POST',
        json: { email, password, sede_id: sedeId ?? null },
      })
      fijarToken(datos.access_token)
      await cargarYo()
    },
    [cargarYo],
  )

  const adoptar = useCallback(
    async (datos: TokenSalida) => {
      fijarToken(datos.access_token)
      // Lo cargado con la sesión anterior (permisos, listas) no debe verse con la nueva.
      clienteQuery.clear()
      await cargarYo()
    },
    [cargarYo, clienteQuery],
  )

  const cerrar = useCallback(async () => {
    try {
      await api('/auth/logout', { method: 'POST' })
    } finally {
      fijarToken(null)
      clienteQuery.clear()
      setEstado({ tipo: 'anonimo' })
    }
  }, [clienteQuery])

  const puede = useCallback(
    (permiso: string) => estado.tipo === 'autenticado' && estado.yo.permisos.includes(permiso),
    [estado],
  )

  const valor = useMemo(
    () => ({ estado, iniciar, cerrar, adoptar, puede }),
    [estado, iniciar, cerrar, adoptar, puede],
  )
  return <ContextoSesion.Provider value={valor}>{children}</ContextoSesion.Provider>
}
