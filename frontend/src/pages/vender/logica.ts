/** Reglas del punto de venta sin interfaz: estado de cada producto y qué falta para cobrar. */
import { calcular, pagosPara, type Carrito, type PagoElegido } from '../../lib/carrito'
import { dec } from '../../lib/decimal'
import type { MetodoPago, Producto } from '../../lib/tipos'

export interface EstadoProducto {
  texto: string
  tono: 'normal' | 'bien' | 'bajo'
  vendible: boolean
}

/** "Se prepara" o "N en vitrina" (en rojo si está en el mínimo o por debajo). */
export function estadoProducto(p: Producto): EstadoProducto {
  if (!p.disponible) return { texto: 'Agotado', tono: 'bajo', vendible: false }
  if (p.tipo === 'preparado') {
    return p.tiene_receta
      ? { texto: 'Se prepara', tono: 'normal', vendible: true }
      : { texto: 'Sin receta', tono: 'bajo', vendible: false }
  }
  const stock = dec(p.stock ?? '0')
  const unidades = stock.toDecimalPlaces(0, 1).toString()
  if (stock.lte(0)) return { texto: 'Sin unidades', tono: 'bajo', vendible: true }
  return { texto: `${unidades} en vitrina`, tono: stock.lte(dec(p.stock_minimo)) ? 'bajo' : 'bien', vendible: true }
}

export interface Cobro {
  elegidos: PagoElegido[]
  /** Con cuánto paga en efectivo (para el cambio); null = exacto. */
  recibido: number | null
}

export const cobroVacio = (): Cobro => ({ elegidos: [], recibido: null })

/** Qué falta para poder cobrar; null si todo está listo. */
export function motivoNoCobrar(carrito: Carrito, cobro: Cobro, metodos: MetodoPago[]): string | null {
  const t = calcular(carrito)
  if (carrito.lineas.length === 0) return 'Agrega productos a la venta.'
  if (t.descuentoExcedido) return 'Un descuento es mayor que el valor al que se aplica.'
  if (carrito.tipoServicio === 'domicilio') {
    if (!carrito.entrega.domiciliarioId) return 'Elige quién lleva el domicilio.'
    if (!carrito.entrega.direccion.trim()) return 'Escribe la dirección de entrega.'
  }
  if (t.cobrar === 0) return null
  if (cobro.elegidos.length === 0) return 'Elige cómo paga.'
  const pagos = pagosPara(t.cobrar, cobro.elegidos)
  if (pagos[0].monto <= 0) return 'Los otros métodos ya cubren todo: quita uno o baja su monto.'
  if (pagos.slice(1).some((p) => p.monto <= 0)) return 'Escribe cuánto paga con cada método.'
  const efectivo = pagos.find((p) => metodos.find((m) => m.id === p.metodoId)?.es_efectivo)
  if (efectivo && cobro.recibido !== null && cobro.recibido < efectivo.monto) return 'Lo recibido en efectivo no alcanza.'
  return null
}

