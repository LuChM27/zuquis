/**
 * Formato de cifras y fechas como en los mockups: `$684.500`, `−$3.000`,
 * `Viernes 16 de octubre`, `5:42 p. m.`. Las fechas se muestran en America/Bogota.
 */
export const ZONA = 'America/Bogota'

const miles = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0, useGrouping: 'always' })

/** Pesos enteros (el backend los envía como entero o como texto). */
export function pesos(valor: number | bigint | string, opciones: { signo?: boolean } = {}): string {
  const n = typeof valor === 'string' ? BigInt(valor) : valor
  const negativo = n < 0
  const abs = negativo ? -n : n
  const texto = `$${miles.format(abs as number | bigint)}`
  if (negativo) return `−${texto}`
  if (opciones.signo && n > 0) return `+${texto}`
  return texto
}

const fechaLarga = new Intl.DateTimeFormat('es-CO', {
  timeZone: ZONA,
  weekday: 'long',
  day: 'numeric',
  month: 'long',
})

/** `Viernes 16 de octubre` */
export function fechaConDia(fecha: Date): string {
  const partes = Object.fromEntries(fechaLarga.formatToParts(fecha).map((p) => [p.type, p.value]))
  const dia = partes.weekday.charAt(0).toUpperCase() + partes.weekday.slice(1)
  return `${dia} ${partes.day} de ${partes.month}`
}

const horaFmt = new Intl.DateTimeFormat('es-CO', {
  timeZone: ZONA,
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
})

/** `5:42 p. m.` (con espacios normales, sin los espacios finos de Intl). */
export function hora(fecha: Date): string {
  return horaFmt.format(fecha).replace(/[\u202f\u00a0]/g, ' ')
}

/** `dd/mm/aaaa` (RNF-10). */
export function fechaCorta(fecha: Date): string {
  return new Intl.DateTimeFormat('es-CO', {
    timeZone: ZONA,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(fecha)
}

/** Saludo según la hora en Bogotá: `Buenos días`, `Buenas tardes`, `Buenas noches`. */
export function saludo(fecha: Date): string {
  const h = Number(
    new Intl.DateTimeFormat('en-US', { timeZone: ZONA, hour: 'numeric', hourCycle: 'h23' }).format(
      fecha,
    ),
  )
  if (h < 12) return 'Buenos días'
  if (h < 19) return 'Buenas tardes'
  return 'Buenas noches'
}

/** Deja solo dígitos: "$ 12.500" → 12500; vacío → null. */
export function leerPesos(texto: string): number | null {
  const digitos = texto.replace(/\D/g, '').replace(/^0+(?=\d)/, '')
  return digitos === '' ? null : Number(digitos)
}
