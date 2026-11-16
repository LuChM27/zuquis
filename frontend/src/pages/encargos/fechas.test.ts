import { describe, expect, it } from 'vitest'
import { diaMesCorto, diasDelMes, entregaIso, etiquetaSemana, lunesDe, sumarDias, tituloDia } from './fechas'

describe('fechas de encargos', () => {
  it('una fecha sin hora se muestra tal cual, sin correrse por la zona horaria', () => {
    expect(diaMesCorto('2026-11-16')).toBe('16 nov')
    expect(diaMesCorto('2026-01-01')).toBe('1 ene')
  })

  it('la semana empieza el lunes', () => {
    expect(lunesDe('2026-10-16')).toBe('2026-10-12') // viernes
    expect(lunesDe('2026-10-12')).toBe('2026-10-12') // lunes
    expect(lunesDe('2026-10-18')).toBe('2026-10-12') // domingo
  })

  it('suma días cruzando meses', () => {
    expect(sumarDias('2026-10-30', 3)).toBe('2026-11-02')
    expect(sumarDias('2026-11-02', -7)).toBe('2026-10-26')
  })

  it('arma la línea de contexto del mockup', () => {
    expect(etiquetaSemana('2026-10-12')).toBe('Semana del 12 al 18 de octubre')
    expect(etiquetaSemana('2026-10-26')).toBe('Semana del 26 de octubre al 1 de noviembre')
  })

  it('titula el día como el mockup', () => {
    expect(tituloDia('2026-10-16', '2026-10-16')).toBe('Para hoy, viernes 16')
    expect(tituloDia('2026-10-17', '2026-10-16')).toBe('Para mañana, sábado 17')
    expect(tituloDia('2026-10-20', '2026-10-16')).toBe('Para el martes 20 de octubre')
  })

  it('el calendario del mes completa semanas de lunes a domingo', () => {
    const dias = diasDelMes('2026-10-01')
    expect(dias[0]).toBe('2026-09-28')
    expect(dias.at(-1)).toBe('2026-11-01')
    expect(dias.length % 7).toBe(0)
  })

  it('la entrega se envía en hora de Colombia', () => {
    expect(entregaIso('2026-10-16', '17:00')).toBe('2026-10-16T17:00:00-05:00')
  })
})
