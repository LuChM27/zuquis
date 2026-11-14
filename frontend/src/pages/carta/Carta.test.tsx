import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { ContextoSesion, type Sesion } from '../../auth/contexto'
import type { CostoReceta, Producto, Receta } from '../../lib/tipos'
import { Carta } from './Carta'

const SEDE = { id: 's1', nombre: 'Punto Barrio El Carmen' }
const PASTEL: Producto = {
  id: 'p1',
  categoria_id: 'c1',
  nombre: 'Pastel de pollo',
  tipo: 'lote',
  precio: 4500,
  foto_url: null,
  disponible: true,
  activo: true,
  stock_minimo: '0.0000',
  dias_vida_util: 2,
  modificadores: [],
  tiene_receta: true,
  stock: '12.0000',
}
const RECETA: Receta = {
  id: 'r1',
  version: 2,
  vigente: true,
  rendimiento: '12.0000',
  creado_en: '2026-11-10T15:00:00Z',
  items: [{ insumo_id: 'i1', insumo: 'Harina', unidad: 'g', cantidad: '600.0000' }],
}
const COSTO: CostoReceta = {
  receta_id: 'r1',
  version: 2,
  rendimiento: '12.0000',
  items: [{ insumo_id: 'i1', insumo: 'Harina', unidad: 'g', cantidad: '600.0000', costo_unitario: '60.000000', costo: 36000 }],
  completo: true,
  costo_receta: 36000,
  costo_unitario: '3000.000000',
  costo_por_unidad: 3000,
  precio: 4500,
  margen: 1500,
  margen_porcentaje: '25.0000',
  margen_minimo: '30.0000',
  margen_bajo: true,
}
const RESPUESTAS: Record<string, unknown> = {
  '/api/v1/categorias': [{ id: 'c1', nombre: 'Salado', orden: 2, icono: 'sandwich', activa: true }],
  '/api/v1/productos?incluir_inactivos=true': [PASTEL],
  '/api/v1/modificadores': [],
  '/api/v1/insumos': [{ id: 'i1', nombre: 'Harina', unidad_base: 'g', stock_minimo: '0', dias_alerta_vencimiento: null, activo: true, presentaciones: [] }],
  '/api/v1/productos/p1/receta': RECETA,
  '/api/v1/productos/p1/costo': COSTO,
  '/api/v1/insumos?incluir_inactivos=true': [
    {
      id: 'i1',
      nombre: 'Harina',
      unidad_base: 'g',
      stock_minimo: '0',
      dias_alerta_vencimiento: null,
      activo: true,
      presentaciones: [{ id: 'pr1', nombre: 'Bulto 50 kg', factor: '50000.0000', activa: true }],
    },
  ],
  '/api/v1/productos/p1/receta/versiones': [RECETA, { ...RECETA, id: 'r0', version: 1, vigente: false }],
}

let peticiones: { url: string; init?: RequestInit }[] = []

function montar(permisos: string[]) {
  peticiones = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      peticiones.push({ url, init })
      if (init?.method === 'PUT') return new Response(JSON.stringify({ ...RECETA, id: 'r2', version: 3 }), { status: 200 })
      return new Response(JSON.stringify(RESPUESTAS[url] ?? []), { status: 200 })
    }),
  )
  const sesion: Sesion = {
    estado: { tipo: 'autenticado', yo: { usuario: { id: 'u', nombre: 'U', email: 'u@z.co' }, sede: SEDE, sedes: [SEDE], roles: [], permisos } },
    iniciar: async () => {},
    cerrar: async () => {},
    adoptar: async () => {},
    puede: (p) => permisos.includes(p),
  }
  const router = createMemoryRouter([{ path: '/carta', element: <Carta /> }], { initialEntries: ['/carta'] })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ContextoSesion.Provider value={sesion}>
        <RouterProvider router={router} />
      </ContextoSesion.Provider>
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('Carta', () => {
  it('el administrador edita datos y precio, y ve el historial de precios', async () => {
    montar(['carta.editar', 'recetas.editar', 'insumos.gestionar'])
    expect(await screen.findByLabelText('Precio de venta')).toHaveValue('4.500')
    expect(screen.getByRole('tab', { name: 'Precios' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Categorías' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Insumos' })).toBeInTheDocument()
  })

  it('producción ve la receta y la puede editar, pero no el precio', async () => {
    montar(['recetas.editar', 'insumos.gestionar'])
    expect(await screen.findByRole('heading', { level: 2, name: 'Pastel de pollo' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Precio de venta')).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Precios' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Categorías' })).not.toBeInTheDocument()
    // Abre directo en la receta, editable.
    expect(await screen.findByRole('button', { name: 'Guardar nueva versión' })).toBeEnabled()
    await userEvent.click(screen.getByRole('tab', { name: 'Datos' }))
    expect(screen.getByText('Los datos y el precio los cambia el administrador.')).toBeInTheDocument()
  })

  it('guarda una versión nueva de la receta', async () => {
    montar(['recetas.editar'])
    const cantidad = await screen.findByLabelText('Cantidad en g')
    await userEvent.clear(cantidad)
    await userEvent.type(cantidad, '650')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar nueva versión' }))
    const put = peticiones.find((p) => p.init?.method === 'PUT')!
    expect(put.url).toBe('/api/v1/productos/p1/receta')
    expect(JSON.parse(put.init!.body as string)).toEqual({
      rendimiento: '12',
      items: [{ insumo_id: 'i1', cantidad: '650' }],
    })
  })

  it('muestra el costo teórico y avisa del margen bajo', async () => {
    montar(['recetas.editar'])
    const costo = await screen.findByRole('region', { name: 'Costo y margen' })
    expect(within(costo).getByText('Costo de la receta (rinde 12)').nextSibling).toHaveTextContent('$36.000')
    expect(within(costo).getByText('Costo por unidad').nextSibling).toHaveTextContent('$3.000')
    expect(within(costo).getByText('$1.500 · 25 %')).toBeInTheDocument()
    expect(within(costo).getByText(/por debajo del 30 % configurado/)).toBeInTheDocument()
    expect(await screen.findByText(/Versión 1 ·/)).toBeInTheDocument()
  })

  it('al cambiar la unidad del insumo, las presentaciones hablan de la nueva unidad', async () => {
    montar(['insumos.gestionar'])
    expect(await screen.findByText('= 50 kg')).toBeInTheDocument()
    expect(screen.getByLabelText('Trae (g)')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Unidad base'), 'ml')
    expect(screen.getByLabelText('Trae (ml)')).toBeInTheDocument()
    expect(screen.getByText('= 50 L')).toBeInTheDocument()
    expect(screen.getByText(/Cambiaste la unidad de g a ml/)).toBeInTheDocument()
  })

  it('el insumo de la receta se busca escribiendo', async () => {
    montar(['recetas.editar'])
    const campo = await screen.findByRole('combobox', { name: 'Insumo' })
    await waitFor(() => expect(campo).toHaveValue('Harina'))
    await userEvent.clear(campo)
    await userEvent.type(campo, 'har')
    expect(screen.getByRole('option', { name: /Harina/ })).toBeInTheDocument()
  })
})
