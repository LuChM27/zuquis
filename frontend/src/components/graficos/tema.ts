/**
 * Colores y formatos de los gráficos, tomados de los tokens de la marca (styles.css). Los hex
 * son el respaldo cuando no hay CSS (pruebas con jsdom).
 */

function token(nombre: string, respaldo: string): string {
  if (typeof document === 'undefined') return respaldo
  const valor = getComputedStyle(document.documentElement).getPropertyValue(nombre).trim()
  return valor || respaldo
}

export const COLORES = {
  fucsia: token('--color-fucsia', '#c42d72'),
  rosaBarra: token('--color-rosa-barra', '#f2a9c6'),
  rosaSuave: token('--color-rosa-suave', '#fce6ef'),
  dorado: token('--color-dorado', '#b08d3c'),
  cafe: token('--color-cafe', '#4a3428'),
  cafeSuave: token('--color-cafe-suave', '#7a5e50'),
  linea: token('--color-linea', '#f4e9e1'),
  pista: token('--color-pista', '#f6ece6'),
  peligro: token('--color-peligro', '#b3261e'),
}

export const FUENTE = 'Montserrat, system-ui, sans-serif'

const decimal = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 1 })

/** Etiqueta corta para barras: `64 mil`, `1,3 M`, `$800`. */
export function enMiles(valor: number): string {
  const abs = Math.abs(valor)
  const signo = valor < 0 ? '−' : ''
  // 999.500 se redondea a 1000 mil: desde ahí se muestra en millones.
  if (abs >= 999_500) return `${signo}${decimal.format(abs / 1_000_000)} M`
  if (abs >= 1_000) return `${signo}${Math.round(abs / 1_000)} mil`
  return `${signo}$${abs}`
}

/** Color por barra: fucsia en la más alta (hora pico), rosa en el resto. */
export function resaltarMaximo(valores: number[]): string[] {
  const max = Math.max(...valores)
  return valores.map((v) => (v === max ? COLORES.fucsia : COLORES.rosaBarra))
}

/** 15 → `3 p. m.` */
export function etiquetaHora(hora: number): string {
  const h = hora % 12 || 12
  return `${h} ${hora < 12 ? 'a. m.' : 'p. m.'}`
}

/** Ejes y textos con la línea visual de la marca (se mezcla en cada opción de ECharts). */
export const BASE = {
  textStyle: { fontFamily: FUENTE, color: COLORES.cafeSuave },
  grid: { left: 8, right: 8, top: 28, bottom: 8, containLabel: true },
  tooltip: { trigger: 'axis' as const, confine: true, textStyle: { fontFamily: FUENTE } },
  animationDuration: 300,
}
