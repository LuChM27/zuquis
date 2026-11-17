import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { ContextoSesion, type Sesion } from '../../auth/contexto'
import { Reportes } from './Reportes'

vi.mock('../../components/graficos/Grafico', () => ({ default: ({ etiqueta }: { etiqueta: string }) => <div aria-label={etiqueta} /> }))

const SEDE = { id: 's1', nombre: 'Punto Barrio El Carmen' }
const VACIO = {
  tipo: 'ventas',
  titulo: 'Ventas',
  sede: 'Punto Barrio El Carmen',
  desde: '2026-11-09',
  hasta: '2026-11-12',
  generado_en: '2026-11-12T20:00:00Z',
  secciones: [{ titulo: 'Por día', columnas: [{ clave: 'dia', titulo: 'Día', tipo: 'fecha' }], filas: [], totales: null }],
}
const GRUPOS: Record<string, unknown> = {
  ganancia: { cascada: { ventas: 0, costo_insumos: 0, regalado: 0, gastos: 0, mermas: 0, ingresos_cancelacion: 0, utilidad: 0 }, costo_pct: [], flujo: [] },
  ventas: { dia_a_dia: [], anterior: [], calor: [], categorias: [] },
  productos: { producido_vendido: [], mas_vendidos: [], menos_vendidos: [] },
  gastos: { mermas: { por_motivo: [], por_item: [] }, por_categoria_mes: [], por_pagar: { con_fecha: { vencidas: 0, esta_semana: 0, proximas: 0 }, sin_fecha: { d0_15: 0, d16_30: 0, d30_mas: 0 } } },
  encargos: { por_semana: [], abonos_sin_entregar: 0, clientes_top: [] },
  cajeros: { por_cajero: [] },
}
let urls: string[] = []

function montar(permisos: string[], ruta = '/reportes') {
  urls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      urls.push(url)
      const grupo = new URL(url, 'http://x').searchParams.get('grupo')
      const cuerpo = grupo ? GRUPOS[grupo] : VACIO
      return new Response(JSON.stringify(cuerpo), { status: 200 })
    }),
  )
  const sesion: Sesion = {
    estado: { tipo: 'autenticado', yo: { usuario: { id: 'u', nombre: 'U', email: 'u@z.co' }, sede: SEDE, sedes: [SEDE], roles: [], permisos } },
    iniciar: async () => {},
    cerrar: async () => {},
    adoptar: async () => {},
    puede: (p) => permisos.includes(p),
  }
  const router = createMemoryRouter([{ path: '/reportes', element: <Reportes /> }], { initialEntries: [ruta] })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ContextoSesion.Provider value={sesion}>
        <RouterProvider router={router} />
      </ContextoSesion.Provider>
    </QueryClientProvider>,
  )
  return router
}

afterEach(() => vi.unstubAllGlobals())

test('el contador ve las dos pestañas y los seis grupos de gráficos', async () => {
  montar(['reportes.ver', 'reportes.exportar'])
  expect(screen.getByRole('tab', { name: 'Gráficos' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: 'Tablas' })).toBeInTheDocument()
  for (const titulo of ['¿Estamos ganando?', '¿Cuándo y qué se vende?', 'Productos', 'Gastos, mermas y proveedores', 'Encargos y clientes', 'Por cajero']) {
    expect(screen.getByRole('heading', { name: titulo })).toBeInTheDocument()
  }
})

test('el cajero solo ve tablas', async () => {
  montar(['reportes.ver_caja_propia'])
  expect(screen.queryByRole('tab', { name: 'Gráficos' })).not.toBeInTheDocument()
  expect(await screen.findByRole('combobox', { name: 'Reporte' })).toBeInTheDocument()
})

test('el atajo "Mes" cambia el rango de las consultas', async () => {
  const router = montar(['reportes.ver'])
  await userEvent.click(screen.getByRole('tab', { name: 'Mes' }))
  await waitFor(() => expect(router.state.location.search).toMatch(/desde=\d{4}-\d{2}-01/))
  await waitFor(() => expect(urls.some((u) => /desde=\d{4}-\d{2}-01/.test(u))).toBe(true))
})

test('sin permiso de exportar no hay botones de Excel ni PDF', async () => {
  montar(['reportes.ver'], '/reportes?vista=tablas')
  await screen.findByRole('combobox', { name: 'Reporte' })
  expect(screen.queryByRole('button', { name: 'Exportar a Excel' })).not.toBeInTheDocument()
})
