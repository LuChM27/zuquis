import { pasosCascada } from './cascada'

test('pasos positivos y negativos sin cruzar el cero', () => {
  const p = pasosCascada([100, -30, -20], 50)
  expect(p.baseArriba).toEqual([0, 70, 50, 0])
  expect(p.valorArriba).toEqual([100, 30, 20, 50])
  expect(p.valorAbajo).toEqual([0, 0, 0, 0])
})

test('cuando los gastos superan las ventas la barra cruza el cero', () => {
  // Ventas 100, gastos 150: el paso va de 100 a −50 → 100 arriba del cero y 50 abajo.
  const p = pasosCascada([100, -150], -50)
  expect(p.baseArriba).toEqual([0, 0, 0])
  expect(p.valorArriba).toEqual([100, 100, 0])
  expect(p.baseAbajo).toEqual([0, 0, 0])
  expect(p.valorAbajo).toEqual([0, -50, -50])
})

test('un paso que ocurre todo bajo cero', () => {
  // Acumulado −50 y otro gasto de 20: va de −50 a −70.
  const p = pasosCascada([100, -150, -20], -70)
  expect(p.baseAbajo[2]).toBe(-50)
  expect(p.valorAbajo[2]).toBe(-20)
  expect(p.valorArriba[2]).toBe(0)
})
