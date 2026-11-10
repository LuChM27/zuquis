import { fechaConDia, fechaCorta, hora, pesos, saludo } from './formato'

describe('pesos', () => {
  it('separa miles con punto', () => {
    expect(pesos(684500)).toBe('$684.500')
    expect(pesos(2840000)).toBe('$2.840.000')
    expect(pesos(600)).toBe('$600')
    expect(pesos(0)).toBe('$0')
  })
  it('usa signo menos tipográfico en negativos', () => {
    expect(pesos(-3000)).toBe('−$3.000')
  })
  it('acepta texto y bigint sin perder precisión', () => {
    expect(pesos('9007199254740993')).toBe('$9.007.199.254.740.993')
    expect(pesos(12500n)).toBe('$12.500')
  })
  it('puede mostrar el signo más', () => {
    expect(pesos(280600, { signo: true })).toBe('+$280.600')
  })
})

describe('fechas en Bogotá', () => {
  // 16/10/2026 5:42 p. m. en Bogotá = 22:42 UTC
  const f = new Date('2026-10-16T22:42:00Z')
  it('fecha con día', () => expect(fechaConDia(f)).toBe('Viernes 16 de octubre'))
  it('hora', () => expect(hora(f)).toBe('5:42 p. m.'))
  it('fecha corta', () => expect(fechaCorta(f)).toBe('16/10/2026'))
  it('saludo', () => {
    expect(saludo(f)).toBe('Buenas tardes')
    expect(saludo(new Date('2026-10-16T13:00:00Z'))).toBe('Buenos días')
    expect(saludo(new Date('2026-10-17T02:00:00Z'))).toBe('Buenas noches')
  })
})
