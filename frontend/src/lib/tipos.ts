/** Tipos de las respuestas del API (ver los schemas.py de cada módulo del backend). */

export interface Permiso {
  clave: string
  descripcion: string
  modulo: string
}

export interface Rol {
  id: string
  nombre: string
  descripcion: string | null
  es_base: boolean
  activo: boolean
  permisos: string[]
  usuarios: number
}

export interface Asignacion {
  rol_id: string
  sede_id: string
}

export interface Usuario {
  id: string
  nombre: string
  email: string
  activo: boolean
  bloqueado: boolean
  ultimo_acceso: string | null
  roles: (Asignacion & { rol_nombre: string })[]
}

export type Titular = 'negocio' | 'dueno'

export interface MetodoPago {
  id: string
  nombre: string
  es_efectivo: boolean
  titular: Titular
  cuenta_puc: string | null
  activo: boolean
  orden: number
}

export interface Sede {
  id: string
  nombre: string
  direccion: string | null
  telefono: string | null
  activa: boolean
}

export interface Configuracion {
  negocio: {
    nombre: string
    logo_url: string | null
    nit: string | null
    direccion: string | null
    telefono: string | null
  }
  /** Porcentaje como texto ("10.0000"), por rol. */
  tope_descuento_por_rol: Record<string, string>
  dias_alerta_vencimiento: number
  permitir_venta_sin_stock: boolean
  impuestos: { activo: boolean; tipo: string | null; tarifa: string; precios_incluyen_impuesto: boolean }
}

/** Nombre visible de cada módulo de permisos. */
export const MODULOS: Record<string, string> = {
  ventas: 'Ventas',
  descuentos: 'Descuentos',
  caja: 'Caja',
  encargos: 'Encargos',
  clientes: 'Clientes',
  gastos: 'Gastos',
  compras: 'Compras',
  proveedores: 'Proveedores',
  produccion: 'Producción',
  inventario: 'Inventario',
  insumos: 'Insumos',
  carta: 'Carta',
  recetas: 'Recetas',
  reportes: 'Reportes',
  config: 'Configuración',
  usuarios: 'Usuarios',
  auditoria: 'Auditoría',
}
