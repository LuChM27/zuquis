import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { coincide } from '../lib/buscar'
import { Buscador } from './Buscador'

const OPCIONES = [
  { valor: 'a', texto: 'Azúcar glas' },
  { valor: 'h', texto: 'Harina de trigo', detalle: 'g' },
  { valor: 'm', texto: 'Mantequilla' },
  { valor: 'x', texto: 'Crema agria', deshabilitada: true },
]

function Prueba({ inicial = '' }: { inicial?: string }) {
  const [valor, setValor] = useState(inicial)
  return (
    <>
      <Buscador etiqueta="Insumo" opciones={OPCIONES} valor={valor} alCambiar={setValor} />
      <output>{valor || 'nada'}</output>
    </>
  )
}

describe('coincide', () => {
  it('ignora tildes y mayúsculas y busca en cualquier parte', () => {
    expect(coincide('Azúcar glas', 'azucar')).toBe(true)
    expect(coincide('Harina de trigo', 'TRIGO')).toBe(true)
    expect(coincide('Harina de trigo', 'trigo harina')).toBe(true)
    expect(coincide('Mantequilla', 'leche')).toBe(false)
  })
})

describe('Buscador', () => {
  it('filtra la lista mientras se escribe y elige con clic', async () => {
    render(<Prueba />)
    const campo = screen.getByRole('combobox', { name: 'Insumo' })
    await userEvent.type(campo, 'har')
    const opciones = screen.getAllByRole('option')
    expect(opciones.map((o) => o.textContent)).toEqual(['Harina de trigog'])
    await userEvent.click(opciones[0])
    expect(screen.getByRole('status')).toHaveTextContent('h')
    expect(campo).toHaveValue('Harina de trigo')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('al enfocar muestra toda la lista', async () => {
    render(<Prueba />)
    await userEvent.click(screen.getByRole('combobox', { name: 'Insumo' }))
    expect(screen.getAllByRole('option')).toHaveLength(4)
  })

  it('se maneja con flechas y Enter, saltando las deshabilitadas', async () => {
    render(<Prueba />)
    const campo = screen.getByRole('combobox', { name: 'Insumo' })
    await userEvent.type(campo, 'a')
    // Coinciden: Azúcar glas, Harina de trigo, Mantequilla, Crema agria (deshabilitada).
    await userEvent.keyboard('{ArrowDown}{ArrowDown}{Enter}')
    expect(screen.getByRole('status')).toHaveTextContent('m')
  })

  it('Esc cierra y vuelve al valor elegido', async () => {
    render(<Prueba inicial="a" />)
    const campo = screen.getByRole('combobox', { name: 'Insumo' })
    expect(campo).toHaveValue('Azúcar glas')
    await userEvent.clear(campo)
    await userEvent.type(campo, 'man')
    await userEvent.keyboard('{Escape}')
    expect(campo).toHaveValue('Azúcar glas')
    expect(screen.getByRole('status')).toHaveTextContent('a')
  })

  it('avisa cuando nada coincide', async () => {
    render(<Prueba />)
    await userEvent.type(screen.getByRole('combobox', { name: 'Insumo' }), 'chocolate')
    expect(screen.getByText('Nada coincide con «chocolate».')).toBeInTheDocument()
  })
})
