/**
 * Geometría de la cascada de utilidad para ECharts con barras apiladas.
 *
 * Cada paso va del acumulado anterior al nuevo. La parte sobre el cero se dibuja con una base
 * transparente más la barra; la parte bajo el cero, igual pero con valores negativos (ECharts
 * apila positivos y negativos por separado). Así una barra puede cruzar el cero y la utilidad
 * puede ser negativa. El último elemento es la barra de la utilidad, desde cero.
 */
export interface PasosCascada {
  baseArriba: number[]
  valorArriba: number[]
  baseAbajo: number[]
  valorAbajo: number[]
}

export function pasosCascada(pasos: number[], utilidad: number): PasosCascada {
  const r: PasosCascada = { baseArriba: [], valorArriba: [], baseAbajo: [], valorAbajo: [] }
  const tramo = (desde: number, hasta: number) => {
    const bajo = Math.min(desde, hasta)
    const alto = Math.max(desde, hasta)
    r.baseArriba.push(Math.max(bajo, 0))
    r.valorArriba.push(Math.max(alto, 0) - Math.max(bajo, 0))
    r.baseAbajo.push(Math.min(alto, 0))
    r.valorAbajo.push(Math.min(bajo, 0) - Math.min(alto, 0))
  }
  let acumulado = 0
  for (const v of pasos) {
    tramo(acumulado, acumulado + v)
    acumulado += v
  }
  tramo(0, utilidad)
  return r
}
