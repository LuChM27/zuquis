import type { FuenteGasto } from '../../lib/tipos'

/** De dónde sale la plata de un gasto. */
export const FUENTES: Record<FuenteGasto, { texto: string; ayuda: string }> = {
  caja: { texto: 'De la caja', ayuda: 'Sale del dinero de la caja abierta y aparece en el cierre.' },
  banco: { texto: 'Del banco', ayuda: 'Se pagó desde una cuenta del negocio; no toca la caja.' },
  duenos: { texto: 'De los dueños', ayuda: 'Lo pagó un dueño de su bolsillo; no toca la caja.' },
}
