/**
 * Fechas de calendario (aaaa-mm-dd) para la semana y el mes de encargos. Se calculan en UTC al
 * mediodía para que ningún cambio de zona mueva el día; la hora de entrega va siempre en
 * hora de Colombia (UTC−5, sin horario de verano).
 */
import { ZONA } from '../../lib/formato'

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado']
export const DIAS_CORTOS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

const aFecha = (iso: string) => new Date(`${iso}T12:00:00Z`)
const aIso = (d: Date) => d.toISOString().slice(0, 10)

export function sumarDias(iso: string, dias: number): string {
  const d = aFecha(iso)
  d.setUTCDate(d.getUTCDate() + dias)
  return aIso(d)
}

/** 0 = lunes … 6 = domingo. */
export const diaDeSemana = (iso: string) => (aFecha(iso).getUTCDay() + 6) % 7

export const lunesDe = (iso: string) => sumarDias(iso, -diaDeSemana(iso))

export const numeroDia = (iso: string) => aFecha(iso).getUTCDate()

export const nombreMes = (iso: string) => MESES[aFecha(iso).getUTCMonth()]

/** "Semana del 12 al 18 de octubre" (o "del 26 de octubre al 1 de noviembre"). */
export function etiquetaSemana(lunes: string): string {
  const domingo = sumarDias(lunes, 6)
  const mismoMes = nombreMes(lunes) === nombreMes(domingo)
  return mismoMes
    ? `Semana del ${numeroDia(lunes)} al ${numeroDia(domingo)} de ${nombreMes(domingo)}`
    : `Semana del ${numeroDia(lunes)} de ${nombreMes(lunes)} al ${numeroDia(domingo)} de ${nombreMes(domingo)}`
}

/** "Para hoy, viernes 16", "Para mañana, sábado 17" o "Para el martes 20 de octubre". */
export function tituloDia(iso: string, hoy: string): string {
  const dia = DIAS[aFecha(iso).getUTCDay()]
  if (iso === hoy) return `Para hoy, ${dia} ${numeroDia(iso)}`
  if (iso === sumarDias(hoy, 1)) return `Para mañana, ${dia} ${numeroDia(iso)}`
  return `Para el ${dia} ${numeroDia(iso)} de ${nombreMes(iso)}`
}

/** "octubre de 2026" */
export const tituloMes = (iso: string) => `${nombreMes(iso)} de ${aFecha(iso).getUTCFullYear()}`

export const primeroDelMes = (iso: string) => `${iso.slice(0, 8)}01`

export function sumarMeses(iso: string, meses: number): string {
  const d = aFecha(primeroDelMes(iso))
  d.setUTCMonth(d.getUTCMonth() + meses)
  return aIso(d)
}

/** Días que muestra el calendario del mes: semanas completas de lunes a domingo. */
export function diasDelMes(primero: string): string[] {
  const inicio = lunesDe(primero)
  const ultimo = sumarDias(sumarMeses(primero, 1), -1)
  const fin = sumarDias(lunesDe(ultimo), 6)
  const dias: string[] = []
  for (let d = inicio; d <= fin; d = sumarDias(d, 1)) dias.push(d)
  return dias
}

/** Día de calendario (en Bogotá) de una fecha con hora del backend. */
export function diaLocal(fecha: string | Date): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: ZONA }).format(new Date(fecha))
}

/** Hora "17:00" (en Bogotá) para el campo de hora. */
export function horaLocal(fecha: string | Date): string {
  return new Intl.DateTimeFormat('en-GB', { timeZone: ZONA, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(fecha))
}

/** Lo que espera el backend: "2026-10-16T17:00:00-05:00". */
export const entregaIso = (dia: string, hora: string) => `${dia}T${hora}:00-05:00`
