import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { ContextoSesion, type Sesion } from '../../auth/contexto'
import type { Dashboard as DatosDashboard } from '../../lib/reportes'
import { Dashboard } from './Dashboard'

vi.mock('../../components/graficos/Grafico', () => ({ default: ({ etiqueta }: { etiqueta: string }) => <div aria-label={etiqueta} /> }))

const SEDE = { id: 's1', nombre: 'Punto Barrio El Carmen' }
const fila = (etiqueta: string, ventas: number, unidades = '0') => ({ clave: etiqueta, etiqueta, ventas, costo: 0, unidades, n: 1 })

function datos(extra: Partial<DatosDashboard> = {}): DatosDashboard {
  return {
    fecha: '2026-10-16',
    caja_abierta_desde: '2026-10-16T20:00:00Z',
    datos_ejemplo: false,
    ventas: 684500,
    n_ventas: 38,
    gastos: 126000,
    n_gastos: 3,
    ganancia: 312800,
    ticket_promedio: 18000,
    por_hora: [fila('15', 64000), fila('18', 168000)],
    por_metodo: [fila('Efectivo', 280600), fila('Nequi', 225900)],
    porcentaje_metodo: { Efectivo: '41.00', Nequi: '33.00' },
    mas_vendidos: [fila('Malteada de brownie', 144000, '9.0000')],
    encargos_hoy: [
      { id: 'e1', numero: 7, descripcion: 'Torta de cumpleaños 1 lb · vainilla', cliente: 'Cliente A', hora: '2026-10-16T22:00:00Z', saldo: 45000, estado: 'listo' },
    ],
    alertas: [{ tipo: 'bajo_minimo', titulo: 'Leche entera bajo el mínimo', detalle: 'Quedan 2 L de un mínimo de 6 L' }],
    ...extra,
  }
}

function montar(d: DatosDashboard) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(d), { status: 200 })))
  const sesion: Sesion = {
    estado: { tipo: 'autenticado', yo: { usuario: { id: 'u', nombre: 'U', email: 'u@z.co' }, sede: SEDE, sedes: [SEDE], roles: [], permisos: ['reportes.ver'] } },
    iniciar: async () => {},
    cerrar: async () => {},
    adoptar: async () => {},
    puede: () => true,
  }
  const router = createMemoryRouter([{ path: '/', element: <Dashboard /> }], { initialEntries: ['/'] })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ContextoSesion.Provider value={sesion}>
        <RouterProvider router={router} />
      </ContextoSesion.Provider>
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

test('muestra las cifras del día como en el mockup', async () => {
  montar(datos())
  expect(await screen.findByText('$684.500')).toBeInTheDocument()
  expect(screen.getByText('38 ventas · sin contar propinas ni domicilios')).toBeInTheDocument()
  expect(screen.getByText('3 gastos registrados')).toBeInTheDocument()
  expect(screen.getByText('$280.600 · 41%')).toBeInTheDocument()
  expect(screen.getByText('9 und')).toBeInTheDocument()
  expect(screen.getByText('Cliente A · Saldo por cobrar $45.000')).toBeInTheDocument()
  expect(screen.getByText('Leche entera bajo el mínimo')).toBeInTheDocument()
  expect(screen.queryByText('Datos de ejemplo')).not.toBeInTheDocument()
})

test('enlaces a encargos, inventario y nueva venta', async () => {
  montar(datos())
  await screen.findByText('$684.500')
  expect(screen.getByRole('link', { name: 'Ir a inventario' })).toHaveAttribute('href', '/inventario')
  expect(screen.getByRole('link', { name: 'Ver todos' })).toHaveAttribute('href', '/encargos')
  expect(screen.getByRole('link', { name: 'Nueva venta' })).toHaveAttribute('href', '/vender')
})

test('chip de datos de ejemplo solo si la sede los tiene', async () => {
  montar(datos({ datos_ejemplo: true }))
  expect(await screen.findByText('Datos de ejemplo')).toBeInTheDocument()
})

test('un encargo ya pagado dice "pagado"', async () => {
  montar(datos({ encargos_hoy: [{ ...datos().encargos_hoy[0], saldo: 0, cliente: 'Cliente B' }] }))
  expect(await screen.findByText('Cliente B · Saldo por cobrar $0 · pagado')).toBeInTheDocument()
})
