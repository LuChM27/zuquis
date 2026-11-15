import { useQuery } from '@tanstack/react-query'
import { useSesion } from '../../auth/contexto'
import { api } from '../../lib/api'
import type { EstadoCaja } from '../../lib/tipos'

export const LECTORES_CAJA = ['caja.abrir', 'caja.cerrar', 'caja.movimientos', 'ventas.crear']

/** Estado de la caja de la sede (abierta desde, responsable, esperado por método). */
export function useCaja() {
  const { puede } = useSesion()
  return useQuery({
    queryKey: ['caja', 'actual'],
    queryFn: () => api<EstadoCaja>('/caja/actual'),
    enabled: LECTORES_CAJA.some(puede),
    // Otro equipo puede abrir o cerrar la caja: se revisa cada minuto.
    refetchInterval: 60_000,
  })
}

/** Por defecto, un pago en efectivo sale de la caja si está abierta; se puede cambiar. */
export function usarDesdeCaja(elegido: boolean | null, esEfectivo: boolean, cajaAbierta: boolean): boolean {
  return cajaAbierta && (elegido ?? esEfectivo)
}
