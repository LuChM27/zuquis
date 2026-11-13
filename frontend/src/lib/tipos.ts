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

// --- Inventario (backend/app/modules/inventario/schemas.py) ---------------------------------

export type TipoItem = 'insumo' | 'producto'
export type EstadoStock = 'bien' | 'bajo_minimo' | 'por_vencer' | 'vencido'

export interface StockItem {
  tipo_item: TipoItem
  item_id: string
  nombre: string
  /** Unidad base: g, ml o und. */
  unidad: string
  /** Lo vigente; lo vencido sin dar de baja va aparte. */
  cantidad: string
  cantidad_vencida: string
  minimo: string
  proximo_vencimiento: string | null
  estado: EstadoStock
  valor: number
  lotes: number
  usado_en_recetas: number
}

export interface ResumenInventario {
  valor_inventario: number
  dias_alerta_vencimiento: number
  bajo_minimo: string[]
  lotes_por_vencer: number
  /** Un nombre por lote que vence pronto. */
  por_vencer: string[]
  mermas_mes: number
}

export interface Lote {
  id: string
  origen: 'compra' | 'produccion' | 'ajuste'
  origen_id: string | null
  cantidad_inicial: string
  cantidad_disponible: string
  costo_unitario: string
  fecha_ingreso: string
  fecha_vencimiento: string | null
  vencido: boolean
  se_usa_primero: boolean
  proveedor: string | null
}

export type TipoMovimiento =
  | 'compra'
  | 'venta'
  | 'consumo_produccion'
  | 'entrada_produccion'
  | 'merma'
  | 'ajuste'
  | 'reverso_anulacion'

export interface Movimiento {
  id: string
  fecha: string
  tipo: TipoMovimiento
  tipo_item: TipoItem
  item_id: string
  item_nombre: string | null
  lote_id: string
  cantidad: string
  costo_unitario: string
  costo_total: number
  referencia_tipo: string
  referencia_id: string
  usuario: string | null
  saldo_cantidad: string | null
  saldo_costo: number | null
}

export interface RecetaUso {
  receta_id: string
  nombre: string
  es_adicion: boolean
  cantidad: string
}

export type MotivoMerma = 'vencido' | 'danado' | 'error_preparacion' | 'degustacion'

export interface Merma {
  id: string
  tipo_item: TipoItem
  item_id: string
  item_nombre: string | null
  lote_id: string | null
  cantidad: string
  motivo: MotivoMerma
  nota: string | null
  costo_total: number
  fecha: string
}

export interface Ajuste {
  id: string
  tipo_item: TipoItem
  item_id: string
  cantidad_sistema: string
  cantidad_contada: string
  diferencia: string
  cantidad_vencida: string
  costo_total: number
  motivo: string
  fecha: string
}

export interface Pagina<T> {
  items: T[]
  total: number
  page: number
  size: number
}
