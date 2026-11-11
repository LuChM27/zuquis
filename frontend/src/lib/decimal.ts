/**
 * Cantidades, costos y porcentajes con decimal.js: nunca `Number` (RNF-01). El backend envía
 * los decimales como texto ("1.5000") y los pesos como enteros.
 */
import Decimal from 'decimal.js'

Decimal.set({ precision: 40, rounding: Decimal.ROUND_HALF_UP })

export { Decimal }

/** Solo acepta texto o Decimal: un número con decimales ya pudo perder precisión. */
export function dec(valor: string | Decimal): Decimal {
  if (typeof valor !== 'string' && !(valor instanceof Decimal)) {
    throw new TypeError('Los decimales deben llegar como texto, no como número.')
  }
  return new Decimal(valor)
}

/** Redondea a peso entero, mitad hacia arriba, una sola vez al final (como el backend). */
export function aPesos(valor: Decimal): number {
  return valor.toDecimalPlaces(0, Decimal.ROUND_HALF_UP).toNumber()
}

/** Porcentaje de un valor en pesos: 10 % de 12.500 = 1.250. */
export function porcentajeDe(pesos: number, porcentaje: string): number {
  return aPesos(new Decimal(pesos).mul(dec(porcentaje)).div(100))
}

/** Costo de una línea: cantidad × costo unitario, redondeado a peso. */
export function costoLinea(cantidad: string, costoUnitario: string): number {
  return aPesos(dec(cantidad).mul(dec(costoUnitario)))
}

/** "1.5000" + "kg" → "1,5 kg"; "1250" + "g" → "1.250 g". Sin ceros sobrantes. */
export function cantidad(valor: string, unidad?: string): string {
  const d = dec(valor)
  const [entera, fraccion] = d.abs().toFixed().split('.')
  const conMiles = entera.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  const texto = `${d.isNegative() ? '−' : ''}${conMiles}${fraccion ? `,${fraccion}` : ''}`
  return unidad ? `${texto} ${unidad}` : texto
}
