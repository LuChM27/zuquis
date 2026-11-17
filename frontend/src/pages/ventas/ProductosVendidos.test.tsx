import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ProductosVendidos } from './ProductosVendidos'

afterEach(() => vi.restoreAllMocks())

describe('lo que se vendió', () => {
  it('las líneas sin producto (personalizados, decoración) no repiten la clave', () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ProductosVendidos
        productos={[
          { producto_id: 'p1', producto: 'Pastel de pollo', cantidad: '2', valor: 9000 },
          { producto_id: null, producto: 'Caja decorada', cantidad: '1', valor: 5000 },
          { producto_id: null, producto: 'Decoración: letras doradas', cantidad: '1', valor: 25000 },
        ]}
      />,
    )
    expect(screen.getByText('Caja decorada')).toBeInTheDocument()
    expect(screen.getByText('Decoración: letras doradas')).toBeInTheDocument()
    expect(error.mock.calls.flat().join(' ')).not.toMatch(/same key/)
  })
})
