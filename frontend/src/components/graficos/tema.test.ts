import { COLORES, enMiles, etiquetaHora, resaltarMaximo } from './tema'

test('enMiles abrevia como en el mockup', () => {
  expect(enMiles(64000)).toBe('64 mil')
  expect(enMiles(1250000)).toBe('1,3 M')
  expect(enMiles(999500)).toBe('1 M')
  expect(enMiles(800)).toBe('$800')
  expect(enMiles(0)).toBe('$0')
})

test('resaltarMaximo pinta en fucsia solo la barra más alta', () => {
  expect(resaltarMaximo([1, 5, 3])).toEqual([COLORES.rosaBarra, COLORES.fucsia, COLORES.rosaBarra])
  expect(resaltarMaximo([])).toEqual([])
})

test('etiquetaHora usa el formato de 12 horas', () => {
  expect(etiquetaHora(15)).toBe('3 p. m.')
  expect(etiquetaHora(0)).toBe('12 a. m.')
  expect(etiquetaHora(12)).toBe('12 p. m.')
})
