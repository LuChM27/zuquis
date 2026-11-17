import type { EstadoEncargo } from '../../lib/tipos'

type Tono = 'exito' | 'peligro' | 'aviso' | 'marca' | 'neutro'

/** Insignias del mockup "Encargos y abonos": Entregado verde, Listo rosa, En producción ámbar, Pendiente neutro. */
export const ESTADOS_ENCARGO: Record<EstadoEncargo, { texto: string; tono: Tono }> = {
  pendiente: { texto: 'Pendiente', tono: 'neutro' },
  en_produccion: { texto: 'En producción', tono: 'aviso' },
  listo: { texto: 'Listo', tono: 'marca' },
  entregado: { texto: 'Entregado', tono: 'exito' },
  cancelado: { texto: 'Cancelado', tono: 'peligro' },
}

/** Los cuatro pasos de la barra de progreso (cancelado no es un paso). */
export const PASOS: EstadoEncargo[] = ['pendiente', 'en_produccion', 'listo', 'entregado']

/** Qué botón lleva al siguiente paso desde cada estado (entregar es aparte: cobra el saldo). */
export const AVANZAR: Partial<Record<EstadoEncargo, { a: EstadoEncargo; texto: string }>> = {
  pendiente: { a: 'en_produccion', texto: 'Pasar a producción' },
  en_produccion: { a: 'listo', texto: 'Marcar como listo' },
}
