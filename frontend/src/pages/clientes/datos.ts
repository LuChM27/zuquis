import { useQuery } from '@tanstack/react-query'
import { api } from '../../lib/api'
import type { Cliente, Domiciliario, MetodoPago, Pagina } from '../../lib/tipos'

/** Clientes activos (hasta 200) para elegir escribiendo; la pantalla de clientes busca en el servidor. */
export function useClientes() {
  return useQuery({
    queryKey: ['clientes', 'activos'],
    queryFn: () => api<Pagina<Cliente>>('/clientes?size=200').then((p) => p.items),
  })
}

export function useDomiciliarios(incluirInactivos = false) {
  return useQuery({
    queryKey: ['domiciliarios', incluirInactivos],
    queryFn: () => api<Domiciliario[]>(`/domiciliarios${incluirInactivos ? '?incluir_inactivos=true' : ''}`),
  })
}

export function useMetodosActivos() {
  return useQuery({
    queryKey: ['metodos-pago'],
    queryFn: () => api<MetodoPago[]>('/metodos-pago'),
    select: (m) => m.filter((x) => x.activo).sort((a, b) => a.orden - b.orden),
  })
}

/** "3001234567" → "300 123 4567"; los fijos de 7 dígitos, "282 1234". */
export function telefonoLegible(telefono: string | null | undefined): string {
  if (!telefono) return ''
  if (telefono.length === 10) return `${telefono.slice(0, 3)} ${telefono.slice(3, 6)} ${telefono.slice(6)}`
  if (telefono.length === 7) return `${telefono.slice(0, 3)} ${telefono.slice(3)}`
  return telefono
}
