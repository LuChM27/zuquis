import { cantidadLegible, costoPorUnidad, vencimientoRelativo } from './unidades'

describe('cantidadLegible', () => {
  it('pasa gramos a kilos desde 1000 g', () => {
    expect(cantidadLegible('2500.0000', 'g')).toBe('2,5 kg')
    expect(cantidadLegible('12500', 'g')).toBe('12,5 kg')
    expect(cantidadLegible('1000', 'g')).toBe('1 kg')
  })
  it('deja los gramos por debajo de 1000', () => {
    expect(cantidadLegible('800.0000', 'g')).toBe('800 g')
    expect(cantidadLegible('0', 'g')).toBe('0 g')
  })
  it('pasa mililitros a litros', () => {
    expect(cantidadLegible('1500', 'ml')).toBe('1,5 L')
    expect(cantidadLegible('250', 'ml')).toBe('250 ml')
  })
  it('las unidades no cambian', () => {
    expect(cantidadLegible('84.0000', 'und')).toBe('84 und')
  })
  it('conserva decimales sin pasar por Number', () => {
    expect(cantidadLegible('1234.5678', 'g')).toBe('1,2345678 kg')
  })
  it('respeta el signo negativo', () => {
    expect(cantidadLegible('-1200', 'g')).toBe('−1,2 kg')
  })
})

describe('costoPorUnidad', () => {
  it('expresa el costo del gramo por kilo', () => {
    expect(costoPorUnidad('3.000000', 'g')).toBe('$3.000 el kg')
    expect(costoPorUnidad('3.400000', 'g')).toBe('$3.400 el kg')
  })
  it('el mililitro por litro y la unidad tal cual', () => {
    expect(costoPorUnidad('4.5', 'ml')).toBe('$4.500 el L')
    expect(costoPorUnidad('704.166667', 'und')).toBe('$704 la und')
  })
})

describe('vencimientoRelativo', () => {
  const hoy = '2026-10-19'
  it('usa palabras para los próximos días', () => {
    expect(vencimientoRelativo('2026-10-19', hoy)).toBe('Hoy')
    expect(vencimientoRelativo('2026-10-20', hoy)).toBe('Mañana')
    expect(vencimientoRelativo('2026-10-21', hoy)).toBe('En 2 días')
    expect(vencimientoRelativo('2026-10-22', hoy)).toBe('En 3 días')
  })
  it('después muestra la fecha corta, con año si es otro', () => {
    expect(vencimientoRelativo('2026-10-30', hoy)).toBe('30 oct')
    expect(vencimientoRelativo('2027-02-10', hoy)).toBe('Feb 2027')
  })
  it('lo pasado está vencido y sin fecha no aplica', () => {
    expect(vencimientoRelativo('2026-10-18', hoy)).toBe('Venció ayer')
    expect(vencimientoRelativo('2026-10-10', hoy)).toBe('Venció el 10 oct')
    expect(vencimientoRelativo(null, hoy)).toBe('No aplica')
  })
})
