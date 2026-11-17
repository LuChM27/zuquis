import { render, screen } from '@testing-library/react'
import { LimitePago } from './PorPagar'

test('una fecha límite pasada se marca como vencida', () => {
  render(<LimitePago fecha="2020-01-15" />)
  expect(screen.getByText('15/01/2020')).toBeInTheDocument()
  expect(screen.getByText('Vencida')).toBeInTheDocument()
})

test('sin fecha límite dice "Sin fecha"', () => {
  render(<LimitePago fecha={null} />)
  expect(screen.getByText('Sin fecha')).toBeInTheDocument()
})

test('una fecha futura no se marca como vencida', () => {
  render(<LimitePago fecha="2999-12-31" />)
  expect(screen.queryByText('Vencida')).not.toBeInTheDocument()
})
