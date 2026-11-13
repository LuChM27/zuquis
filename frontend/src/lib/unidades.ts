/**
 * Cantidades en la unidad que se lee en el local: "2,5 kg" en vez de "2500 g", "1,5 L" en vez
 * de "1500 ml". Todo con decimal.js (nunca Number) y fechas de vencimiento relativas.
 */
import { aPesos, cantidad, dec } from './decimal'
import { pesos } from './formato'

/** Unidad mayor de cada unidad base: desde 1000 se muestra en ella. */
const MAYOR: Record<string, { unidad: string; factor: number; articulo: string }> = {
  g: { unidad: 'kg', factor: 1000, articulo: 'el' },
  ml: { unidad: 'L', factor: 1000, articulo: 'el' },
}

export function cantidadLegible(valor: string, unidad: string): string {
  const mayor = MAYOR[unidad]
  const d = dec(valor)
  if (mayor && d.abs().gte(mayor.factor)) return cantidad(d.div(mayor.factor).toFixed(), mayor.unidad)
  return cantidad(d.toFixed(), unidad)
}

/** Costo unitario de la unidad base expresado como se compra: "$3.000 el kg", "$450 la und". */
export function costoPorUnidad(costoUnitario: string, unidad: string): string {
  const mayor = MAYOR[unidad]
  if (mayor) return `${pesos(aPesos(dec(costoUnitario).mul(mayor.factor)))} ${mayor.articulo} ${mayor.unidad}`
  return `${pesos(aPesos(dec(costoUnitario)))} la ${unidad}`
}

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

/** Días entre dos fechas ISO (aaaa-mm-dd), sin zona horaria de por medio. */
export function diasEntre(desde: string, hasta: string): number {
  const a = Date.UTC(+desde.slice(0, 4), +desde.slice(5, 7) - 1, +desde.slice(8, 10))
  const b = Date.UTC(+hasta.slice(0, 4), +hasta.slice(5, 7) - 1, +hasta.slice(8, 10))
  return Math.round((b - a) / 86_400_000)
}

/** "20 oct" (mismo año que hoy) o "Feb 2027". */
export function fechaDiaMes(iso: string, hoy: string): string {
  const mes = MESES[+iso.slice(5, 7) - 1]
  if (iso.slice(0, 4) !== hoy.slice(0, 4)) return `${mes.charAt(0).toUpperCase()}${mes.slice(1)} ${iso.slice(0, 4)}`
  return `${+iso.slice(8, 10)} ${mes}`
}

/** Como en la columna "Próximo vencimiento" del mockup: Mañana, En 2 días, 30 oct, Feb 2027. */
export function vencimientoRelativo(iso: string | null, hoy: string): string {
  if (!iso) return 'No aplica'
  const dias = diasEntre(hoy, iso)
  if (dias === 0) return 'Hoy'
  if (dias === 1) return 'Mañana'
  if (dias > 1 && dias <= 3) return `En ${dias} días`
  if (dias === -1) return 'Venció ayer'
  if (dias < 0) return `Venció el ${fechaDiaMes(iso, hoy)}`
  return fechaDiaMes(iso, hoy)
}

/** Fecha aaaa-mm-dd → "13/11/2026", sin pasar por zona horaria. */
export const fechaIso = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`

/** Fecha de hoy en Bogotá como aaaa-mm-dd. */
export function hoyIso(ahora: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota' }).format(ahora)
}
