import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { ContextoSesion, type Sesion } from '../../auth/contexto'
import { Configuracion } from './Configuracion'

const SEDE = { id: 's1', nombre: 'Punto Barrio El Carmen', direccion: null, telefono: null, activa: true }
const ROL_ADMIN = { id: 'r1', nombre: 'Dueño / Admin', descripcion: 'Acceso total', es_base: true, activo: true, permisos: ['usuarios.gestionar', 'config.editar'], usuarios: 1 }
const ROL_CAJERO = { id: 'r2', nombre: 'Cajero / Vendedor', descripcion: null, es_base: true, activo: true, permisos: ['ventas.crear'], usuarios: 0 }

const RESPUESTAS: Record<string, unknown> = {
  '/api/v1/usuarios': [
    { id: 'u1', nombre: 'Administrador', email: 'admin@zuquis.local', activo: true, bloqueado: false, ultimo_acceso: null, roles: [{ rol_id: 'r1', sede_id: 's1', rol_nombre: 'Dueño / Admin' }] },
  ],
  '/api/v1/roles': [ROL_ADMIN, ROL_CAJERO],
  '/api/v1/sedes': [SEDE],
  '/api/v1/permisos': [
    { clave: 'ventas.crear', descripcion: 'Vender, cobrar y registrar propinas', modulo: 'ventas' },
    { clave: 'usuarios.gestionar', descripcion: 'Administrar usuarios y roles', modulo: 'usuarios' },
  ],
  '/api/v1/metodos-pago?solo_activos=false': [
    { id: 'm1', nombre: 'Efectivo', es_efectivo: true, titular: 'negocio', cuenta_puc: '1105', activo: true, orden: 0 },
  ],
  '/api/v1/configuracion': {
    negocio: { nombre: "Zuqui's Repostería", logo_url: null, nit: null, direccion: null, telefono: null },
    tope_descuento_por_rol: { r2: '10.0000' },
    dias_alerta_vencimiento: 3,
    permitir_venta_sin_stock: false,
    margen_minimo: '30.0000',
    impuestos: { activo: false, tipo: null, tarifa: '0.0000', precios_incluyen_impuesto: true },
  },
}

const sesion: Sesion = {
  estado: {
    tipo: 'autenticado',
    yo: {
      usuario: { id: 'u1', nombre: 'Administrador', email: 'admin@zuquis.local' },
      sede: SEDE,
      sedes: [SEDE],
      roles: ['Dueño / Admin'],
      permisos: ['usuarios.gestionar', 'config.editar'],
    },
  },
  iniciar: async () => {},
  cerrar: async () => {},
  adoptar: async () => {},
  puede: () => true,
}

function montar(ruta = '/configuracion') {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => new Response(JSON.stringify(RESPUESTAS[url] ?? {}), { status: 200 })),
  )
  const router = createMemoryRouter([{ path: '/configuracion', element: <Configuracion /> }], { initialEntries: [ruta] })
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ContextoSesion.Provider value={sesion}>
        <RouterProvider router={router} />
      </ContextoSesion.Provider>
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('Configuración', () => {
  it('lista usuarios y abre el detalle del primero', async () => {
    montar()
    expect(await screen.findByRole('heading', { name: 'Administrador' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Usuarios' })).toHaveAttribute('aria-selected', 'true')
  })

  it('valida el usuario nuevo antes de enviarlo', async () => {
    montar()
    await screen.findByRole('heading', { name: 'Administrador' })
    await userEvent.click(screen.getByRole('button', { name: /Nuevo usuario/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Crear usuario' }))
    expect(screen.getByText('La contraseña necesita al menos 8 caracteres.')).toBeInTheDocument()
    expect(screen.getByText('Asigna al menos un rol.')).toBeInTheDocument()
  })

  it('muestra los topes de descuento por rol en la sección Negocio', async () => {
    montar('/configuracion?seccion=negocio')
    const tope = await screen.findByLabelText('Tope de descuento de Cajero / Vendedor, en porcentaje')
    expect(tope).toHaveValue('10')
    // Sin tope guardado se muestra 0, no un campo vacío.
    expect(screen.getByLabelText('Tope de descuento de Dueño / Admin, en porcentaje')).toHaveValue('0')
  })

  it('pide confirmación con el nombre antes de eliminar un rol', async () => {
    RESPUESTAS['/api/v1/roles'] = [ROL_ADMIN, { ...ROL_CAJERO, es_base: false }]
    montar('/configuracion?seccion=roles')
    await userEvent.click(await screen.findByText('Cajero / Vendedor'))
    await userEvent.click(screen.getByRole('button', { name: 'Eliminar rol' }))
    expect(screen.getByRole('button', { name: 'Eliminar «Cajero / Vendedor»' })).toBeInTheDocument()
  })
})
