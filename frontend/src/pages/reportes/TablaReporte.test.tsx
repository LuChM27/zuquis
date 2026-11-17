import { render, screen, within } from '@testing-library/react'
import type { Seccion } from '../../lib/reportes'
import { TablaReporte } from './TablaReporte'

const SECCION: Seccion = {
  titulo: 'Arqueos',
  columnas: [
    { clave: 'metodo', titulo: 'Método', tipo: 'texto' },
    { clave: 'dia', titulo: 'Día', tipo: 'fecha' },
    { clave: 'margen', titulo: 'Margen', tipo: 'porcentaje' },
    { clave: 'unidades', titulo: 'Unidades', tipo: 'cantidad' },
    { clave: 'diferencia', titulo: 'Diferencia', tipo: 'pesos' },
  ],
  filas: [{ metodo: 'Efectivo', dia: '2026-11-10', margen: '41.20', unidades: '2.5000', diferencia: -12000 }],
  totales: { diferencia: -12000 },
}

test('formatea cada celda según su tipo', () => {
  render(<TablaReporte seccion={SECCION} />)
  const tabla = within(screen.getByRole('table'))
  expect(tabla.getAllByText('−$12.000')[0]).toHaveClass('text-peligro-texto')
  expect(tabla.getByText('41,2 %')).toBeInTheDocument()
  expect(tabla.getByText('10/11/2026')).toBeInTheDocument()
  expect(tabla.getByText('2,5')).toBeInTheDocument()
})

test('muestra los totales al pie', () => {
  render(<TablaReporte seccion={SECCION} />)
  const tabla = within(screen.getByRole('table'))
  expect(tabla.getByText('Total')).toBeInTheDocument()
  expect(tabla.getAllByText('−$12.000')).toHaveLength(2)
})

test('sección sin filas dice que no hay datos', () => {
  render(<TablaReporte seccion={{ ...SECCION, filas: [], totales: null }} />)
  expect(screen.getByText('Sin datos en este rango')).toBeInTheDocument()
})
