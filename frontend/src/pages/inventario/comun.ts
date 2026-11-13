import { useSyncExternalStore } from 'react'
import { dec } from '../../lib/decimal'
import type { EstadoStock, MotivoMerma, StockItem, TipoMovimiento } from '../../lib/tipos'
import { cantidadLegible } from '../../lib/unidades'

export const ESTADOS: Record<EstadoStock, { texto: string; tono: 'exito' | 'peligro' | 'aviso' }> = {
  bien: { texto: 'Bien', tono: 'exito' },
  bajo_minimo: { texto: 'Bajo el mínimo', tono: 'peligro' },
  por_vencer: { texto: 'Por vencer', tono: 'aviso' },
  vencido: { texto: 'Vencido', tono: 'peligro' },
}

/** Fondo de la fila según el estado, como en el mockup (rosado o amarillo muy claro). */
export const FONDO_FILA: Record<EstadoStock, string> = {
  bien: '',
  bajo_minimo: 'bg-peligro-fila',
  vencido: 'bg-peligro-fila',
  por_vencer: 'bg-aviso-fila',
}

export const MOVIMIENTOS: Record<TipoMovimiento, string> = {
  compra: 'Compra',
  venta: 'Venta',
  consumo_produccion: 'Consumo en producción',
  entrada_produccion: 'Producción',
  merma: 'Merma',
  ajuste: 'Ajuste por conteo',
  reverso_anulacion: 'Anulación',
}

export const MOTIVOS: Record<MotivoMerma, string> = {
  vencido: 'Vencido',
  danado: 'Dañado',
  error_preparacion: 'Error de preparación',
  degustacion: 'Degustación',
}

/**
 * Lo que se escribe en un campo de cantidad: "2,5" o "2.5" → "2.5". Sin separador de miles y
 * máximo 4 decimales, como acepta el backend. Vacío o inválido → null.
 */
export function leerCantidad(texto: string): string | null {
  const limpio = texto.trim().replace(',', '.')
  if (!/^\d+(\.\d{1,4})?$/.test(limpio)) return null
  return limpio
}

/** "Leche entera, mantequilla, azúcar glas": primera en mayúscula, el resto en minúscula. */
export function listaNatural(nombres: string[]): string {
  return nombres.map((n, i) => (i === 0 ? n : n.charAt(0).toLowerCase() + n.slice(1))).join(', ')
}

/** "Fresas, crema de leche, 2 de queso": agrupa los lotes por ítem. */
export function lotesPorItem(nombres: string[]): string {
  const cuenta = new Map<string, number>()
  for (const n of nombres) cuenta.set(n, (cuenta.get(n) ?? 0) + 1)
  return listaNatural([...cuenta].map(([n, c]) => (c > 1 ? `${c} de ${n.toLowerCase()}` : n)))
}

const CONSULTA_CELULAR = '(max-width: 1023px)'

/** true en celular y tableta vertical: el detalle va en hoja inferior en vez de panel lateral. */
export function useEsCelular(): boolean {
  return useSyncExternalStore(
    (avisar) => {
      const m = window.matchMedia?.(CONSULTA_CELULAR)
      m?.addEventListener('change', avisar)
      return () => m?.removeEventListener('change', avisar)
    },
    () => window.matchMedia?.(CONSULTA_CELULAR).matches ?? false,
  )
}

const RUTA = { insumo: 'insumos', producto: 'productos' } as const

export function rutaItem(item: Pick<StockItem, 'tipo_item' | 'item_id'>): string {
  return `/${RUTA[item.tipo_item]}/${item.item_id}`
}

/** Subtítulo del detalle: "12,5 kg en 2 lotes · se gasta primero el lote más antiguo". */
export function resumenItem(item: StockItem): string {
  const partes = [`${cantidadLegible(item.cantidad, item.unidad)} en ${item.lotes} ${item.lotes === 1 ? 'lote' : 'lotes'}`]
  if (item.lotes > 1) partes.push('se gasta primero el lote más antiguo')
  if (dec(item.cantidad_vencida).gt(0)) {
    partes.push(`${cantidadLegible(item.cantidad_vencida, item.unidad)} vencido por dar de baja`)
  }
  return partes.join(' · ')
}

