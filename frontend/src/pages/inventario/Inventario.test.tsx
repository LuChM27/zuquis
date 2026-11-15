import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { ContextoSesion, type Sesion } from '../../auth/contexto'
import type { Lote, ResumenInventario, StockItem } from '../../lib/tipos'
import { Inventario } from './Inventario'

const SEDE = { id: 's1', nombre: 'Punto Barrio El Carmen' }

const base = { cantidad_vencida: '0.0000', valor: 0, lotes: 1, usado_en_recetas: 0, proximo_vencimiento: null }
const STOCK: StockItem[] = [
  { ...base, tipo_item: 'insumo', item_id: 'harina', nombre: 'Harina de trigo', unidad: 'g', cantidad: '12500.0000', minimo: '5000.0000', estado: 'bien', lotes: 2, usado_en_recetas: 9 },
  { ...base, tipo_item: 'insumo', item_id: 'leche', nombre: 'Leche entera', unidad: 'ml', cantidad: '2000.0000', minimo: '6000.0000', estado: 'bajo_minimo' },
  { ...base, tipo_item: 'producto', item_id: 'pastel', nombre: 'Pastel de pollo', unidad: 'und', cantidad: '12.0000', minimo: '0.0000', estado: 'bien' },
]
const RESUMEN: ResumenInventario = {
  valor_inventario: 2840000,
  dias_alerta_vencimiento: 3,
  bajo_minimo: ['Leche entera', 'Mantequilla', 'Azúcar glas'],
  lotes_por_vencer: 4,
  por_vencer: ['Fresas', 'Crema de leche', 'Queso', 'Queso'],
  mermas_mes: 84300,
}
const lote = (id: string, extra: Partial<Lote>): Lote => ({
  id,
  origen: 'compra',
  origen_id: null,
  cantidad_inicial: '10000.0000',
  cantidad_disponible: '10000.0000',
  costo_unitario: '3.000000',
  fecha_ingreso: '2026-10-06T15:00:00Z',
  fecha_vencimiento: null,
  vencido: false,
  se_usa_primero: false,
  proveedor: 'Proveedor A',
  ...extra,
})
const RESPUESTAS: Record<string, unknown> = {
  '/api/v1/inventario/stock': STOCK,
  '/api/v1/inventario/resumen': RESUMEN,
  '/api/v1/insumos/harina/lotes': [
    lote('l1', { cantidad_disponible: '2500.0000', se_usa_primero: true }),
    lote('l2', { fecha_ingreso: '2026-10-13T15:00:00Z', costo_unitario: '4.000000' }),
  ],
  '/api/v1/insumos/harina/recetas': ['Pastel de pollo', 'Croissant', 'Brownie', 'Tortas', 'Pan', 'Galletas', 'Muffin', 'Cheesecake', 'Pie'].map(
    (nombre, i) => ({ receta_id: `r${i}`, nombre, es_adicion: false, cantidad: '100.0000' }),
  ),
  '/api/v1/insumos/leche/lotes': [lote('l3', { cantidad_inicial: '6000.0000', cantidad_disponible: '2000.0000', costo_unitario: '4.500000', se_usa_primero: true })],
  '/api/v1/insumos/leche/recetas': [],
}

const sesion: Sesion = {
  estado: {
    tipo: 'autenticado',
    yo: { usuario: { id: 'u1', nombre: 'Admin', email: 'a@z.co' }, sede: SEDE, sedes: [SEDE], roles: [], permisos: [] },
  },
  iniciar: async () => {},
  cerrar: async () => {},
  adoptar: async () => {},
  puede: () => true,
}

let peticiones: { url: string; init?: RequestInit }[] = []

function montar() {
  peticiones = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      peticiones.push({ url, init })
      if (url === '/api/v1/mermas' && init?.method === 'POST') {
        return new Response(
          JSON.stringify({ id: 'm1', tipo_item: 'insumo', item_id: 'harina', item_nombre: 'Harina de trigo', lote_id: null, cantidad: '500.0000', motivo: 'danado', nota: null, costo_total: 1500, fecha: '2026-10-19T15:00:00Z' }),
          { status: 201 },
        )
      }
      return new Response(JSON.stringify(RESPUESTAS[url] ?? {}), { status: 200 })
    }),
  )
  const router = createMemoryRouter([{ path: '/inventario', element: <Inventario /> }], { initialEntries: ['/inventario'] })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ContextoSesion.Provider value={sesion}>
        <RouterProvider router={router} />
      </ContextoSesion.Provider>
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('Inventario', () => {
  it('muestra las cuatro tarjetas como en el mockup', async () => {
    montar()
    expect(await screen.findByText('$2.840.000')).toBeInTheDocument()
    expect(screen.getByText('3 insumos')).toBeInTheDocument()
    expect(screen.getByText('Leche entera, mantequilla, azúcar glas')).toBeInTheDocument()
    expect(screen.getByText('Vencen en 3 días o menos')).toBeInTheDocument()
    expect(screen.getByText('Fresas, crema de leche, 2 de queso')).toBeInTheDocument()
    expect(screen.getByText('$84.300')).toBeInTheDocument()
  })

  it('lista los insumos con unidades legibles y cuenta cada pestaña', async () => {
    montar()
    const fila = (await screen.findByText('Harina de trigo', { selector: 'td' })).closest('tr')!
    expect(within(fila).getByText('12,5 kg')).toBeInTheDocument()
    expect(within(fila).getByText('5 kg')).toBeInTheDocument()
    expect(within(fila).getByText('No aplica')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Insumos (2)' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Productos en vitrina (1)' })).toBeInTheDocument()
    expect(screen.getByText('Bajo el mínimo', { selector: 'span' })).toBeInTheDocument()
  })

  it('el detalle muestra los lotes en orden PEPS y las recetas', async () => {
    montar()
    const detalle = await screen.findByRole('heading', { level: 2, name: 'Harina de trigo' })
    const panel = detalle.closest('section')!
    expect(within(panel).getByText('12,5 kg en 2 lotes · se gasta primero el lote más antiguo')).toBeInTheDocument()
    expect(await within(panel).findByText('Se usa primero')).toBeInTheDocument()
    expect(within(panel).getByText('Siguiente')).toBeInTheDocument()
    expect(within(panel).getByText('Compra de 10 kg a $3.000 el kg · Proveedor A')).toBeInTheDocument()
    expect(within(panel).getByText('Quedan 2,5 kg')).toBeInTheDocument()
    expect(within(panel).getByText('Se usa en 9 recetas')).toBeInTheDocument()
    expect(
      await within(panel).findByText('Pastel de pollo, croissant, brownie, tortas y 5 más. Cada venta o producción descuenta lo que gasta.'),
    ).toBeInTheDocument()
  })

  it('al elegir otra fila cambia el detalle', async () => {
    montar()
    await userEvent.click(await screen.findByText('Leche entera', { selector: 'td' }))
    expect(await screen.findByRole('heading', { level: 2, name: 'Leche entera' })).toBeInTheDocument()
    expect(await screen.findByText('Compra de 6 L a $4.500 el L · Proveedor A')).toBeInTheDocument()
  })

  it('registra una merma con clave de idempotencia', async () => {
    montar()
    await screen.findByText('Harina de trigo', { selector: 'td' })
    await userEvent.click(screen.getAllByRole('button', { name: 'Registrar merma' })[0])
    const dialogo = await screen.findByRole('dialog', { name: 'Registrar merma' })
    await userEvent.type(within(dialogo).getByRole('combobox', { name: 'Insumo o producto' }), 'harina')
    await userEvent.click(within(dialogo).getByRole('option', { name: /Harina de trigo/ }))
    await userEvent.type(within(dialogo).getByLabelText('Cantidad (g)'), '500')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Registrar merma' }))
    const post = peticiones.find((p) => p.url === '/api/v1/mermas')!
    expect(JSON.parse(post.init!.body as string)).toMatchObject({
      tipo_item: 'insumo',
      item_id: 'harina',
      lote_id: null,
      cantidad: '500',
      motivo: 'danado',
    })
    expect(new Headers(post.init!.headers).get('Idempotency-Key')).toMatch(/[0-9a-f-]{36}/)
  })

  it('filtra la tabla escribiendo, sin importar tildes', async () => {
    montar()
    await screen.findByText('Harina de trigo', { selector: 'td' })
    await userEvent.type(screen.getByRole('searchbox', { name: 'Buscar insumo' }), 'LECHE')
    expect(screen.queryByText('Harina de trigo', { selector: 'td' })).not.toBeInTheDocument()
    expect(screen.getByText('Leche entera', { selector: 'td' })).toBeInTheDocument()
  })
})
