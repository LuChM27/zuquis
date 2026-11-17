import { atajo, TIPOS_VISIBLES } from './reportes'

const jueves = new Date('2026-11-12T12:00:00-05:00')

test('atajos de fecha en Bogotá', () => {
  expect(atajo('hoy', jueves)).toEqual({ desde: '2026-11-12', hasta: '2026-11-12' })
  expect(atajo('ayer', jueves)).toEqual({ desde: '2026-11-11', hasta: '2026-11-11' })
  expect(atajo('semana', jueves)).toEqual({ desde: '2026-11-09', hasta: '2026-11-12' })
  expect(atajo('mes', jueves)).toEqual({ desde: '2026-11-01', hasta: '2026-11-12' })
})

test('la semana empieza el lunes aunque hoy sea domingo', () => {
  expect(atajo('semana', new Date('2026-11-15T20:00:00-05:00'))).toEqual({ desde: '2026-11-09', hasta: '2026-11-15' })
})

test('tipos de reporte visibles según el rol', () => {
  expect(TIPOS_VISIBLES(['reportes.ver_inventario'])).toEqual(['inventario-valorizado', 'mermas'])
  expect(TIPOS_VISIBLES(['reportes.ver_caja_propia'])).toEqual(['ventas'])
  expect(TIPOS_VISIBLES(['reportes.ver'])).toContain('puc')
})
