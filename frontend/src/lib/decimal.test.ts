import { aPesos, cantidad, costoLinea, dec, porcentajeDe } from './decimal'
import { leerPesos, leerPesosPegados } from './formato'

describe('decimales', () => {
  it('rechaza números: los decimales viajan como texto', () => {
    expect(() => dec(0.1 as unknown as string)).toThrow(TypeError)
    expect(dec('0.1').plus(dec('0.2')).toString()).toBe('0.3')
  })

  it('redondea a peso mitad hacia arriba', () => {
    expect(aPesos(dec('12.5'))).toBe(13)
    expect(aPesos(dec('12.4999'))).toBe(12)
    expect(aPesos(dec('-12.5'))).toBe(-13)
  })

  it('porcentajes como en el backend', () => {
    expect(porcentajeDe(12500, '10')).toBe(1250)
    expect(porcentajeDe(9000, '33.3333')).toBe(3000)
  })

  it('costo de línea con costo unitario de 6 decimales', () => {
    // 2,5 kg de harina a $3.000/kg
    expect(costoLinea('2.5000', '3000.000000')).toBe(7500)
    expect(costoLinea('0.3333', '4200.000000')).toBe(1400)
  })

  it('muestra cantidades sin ceros sobrantes y con coma decimal', () => {
    expect(cantidad('1.5000', 'kg')).toBe('1,5 kg')
    expect(cantidad('84.0000', 'und')).toBe('84 und')
    expect(cantidad('1250', 'g')).toBe('1.250 g')
    expect(cantidad('-0.2500')).toBe('−0,25')
  })
})

describe('campo de dinero', () => {
  it('lee solo dígitos', () => {
    expect(leerPesos('$ 390.000')).toBe(390000)
    expect(leerPesos('007')).toBe(7)
    expect(leerPesos('')).toBeNull()
    expect(leerPesos('abc')).toBeNull()
  })
  it('al escribir, borrar un dígito de 1.000 deja 100 (no centavos)', () => {
    expect(leerPesos('1.00')).toBe(100)
  })
  it('al pegar, no confunde centavos con miles', () => {
    expect(leerPesosPegados('12.500,00')).toBe(12500)
    expect(leerPesosPegados('12500.50')).toBe(12501)
    expect(leerPesosPegados('12500,4')).toBe(12500)
    expect(leerPesosPegados('$ 1.250.000')).toBe(1250000)
    expect(leerPesosPegados('12.500')).toBe(12500)
    expect(leerPesosPegados('')).toBeNull()
  })
})
