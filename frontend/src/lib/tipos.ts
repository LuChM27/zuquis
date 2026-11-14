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
  /** Margen mínimo de las recetas en % ("30.0000"): por debajo, el costeo avisa. */
  margen_minimo: string
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

// --- Carta y recetas (backend/app/modules/carta/schemas.py) ---------------------------------

export interface Categoria {
  id: string
  nombre: string
  orden: number
  /** Nombre del ícono de lucide en kebab-case ("croissant", "cup-soda"). */
  icono: string | null
  activa: boolean
}

export interface Adicion {
  id: string
  nombre: string
  precio: number
  activo: boolean
  tiene_receta: boolean
}

export type TipoProducto = 'preparado' | 'lote'

export interface Producto {
  id: string
  categoria_id: string
  nombre: string
  tipo: TipoProducto
  precio: number
  foto_url: string | null
  disponible: boolean
  activo: boolean
  stock_minimo: string
  dias_vida_util: number | null
  modificadores: Adicion[]
  tiene_receta: boolean
  stock: string | null
}

export interface CambioPrecio {
  precio_anterior: number | null
  precio_nuevo: number
  usuario: string | null
  fecha: string
}

export interface Receta {
  id: string
  version: number
  vigente: boolean
  rendimiento: string
  creado_en: string
  items: { insumo_id: string; insumo: string; unidad: string; cantidad: string }[]
}

export interface CostoReceta {
  receta_id: string
  version: number
  rendimiento: string
  items: {
    insumo_id: string
    insumo: string
    unidad: string
    cantidad: string
    costo_unitario: string | null
    costo: number | null
  }[]
  completo: boolean
  costo_receta: number
  costo_unitario: string
  costo_por_unidad: number
  precio: number
  margen: number
  margen_porcentaje: string | null
  margen_minimo: string
  margen_bajo: boolean
}

export interface Presentacion {
  id: string
  nombre: string
  factor: string
  activa: boolean
}

export interface Insumo {
  id: string
  nombre: string
  unidad_base: string
  stock_minimo: string
  dias_alerta_vencimiento: number | null
  activo: boolean
  presentaciones: Presentacion[]
}

// --- Compras, proveedores y producción ------------------------------------------------------

export interface Proveedor {
  id: string
  nombre: string
  nit_o_cedula: string | null
  telefono: string | null
  email: string | null
  activo: boolean
  insumos: { id: string; nombre: string }[]
}

export type EstadoPago = 'contado' | 'por_pagar' | 'pagada'

export interface CompraItem {
  id: string
  insumo_id: string
  insumo: string
  unidad: string
  presentacion: string | null
  cantidad: string
  cantidad_base: string
  costo_total: number
  costo_unitario: string
  fecha_vencimiento: string | null
  lote_id: string | null
}

export interface PagoCompra {
  id: string
  fecha: string
  monto: number
  metodo_pago_id: string
  metodo_pago: string | null
}

export interface Compra {
  id: string
  proveedor_id: string | null
  proveedor: string | null
  fecha: string
  numero_factura_proveedor: string | null
  total: number
  pagado: number
  saldo: number
  estado_pago: EstadoPago
  soporte_url: string | null
  anulada: boolean
  motivo_anulacion: string | null
  creado_en: string
  items: CompraItem[]
  pagos: PagoCompra[]
}

export interface CuentaPorPagar {
  proveedor_id: string | null
  proveedor: string
  compras: number
  saldo: number
  mas_antigua: string
}

export interface Consumo {
  insumo_id: string
  insumo: string
  unidad: string
  cantidad: string
  costo_total: number
}

export interface VistaPreviaProduccion {
  producto_id: string
  producto: string
  receta_version: number
  cantidad_producida: string
  costo_total: number
  costo_unitario: string
  fecha_vencimiento: string | null
  consumos: Consumo[]
}

export interface Produccion extends VistaPreviaProduccion {
  id: string
  receta_id: string
  lote_resultante_id: string | null
  responsable: string | null
  fecha: string
  anulada: boolean
  motivo_anulacion: string | null
}

// --- Caja y ventas (backend/app/modules/caja y ventas/schemas.py) ---------------------------

export interface SesionCaja {
  id: string
  estado: 'abierta' | 'cerrada'
  abierta_en: string
  abierta_por: string
  responsable: string | null
  base_inicial: number
  cerrada_en: string | null
  cerrada_por: string | null
  observacion: string | null
}

export interface EstadoCaja {
  abierta: boolean
  sesion: SesionCaja | null
  esperado: { metodo_pago_id: string; metodo: string; es_efectivo: boolean; esperado: number }[]
}

export type TipoServicio = 'local' | 'llevar' | 'domicilio'

export interface DescuentoEntrada {
  tipo: 'valor' | 'porcentaje'
  /** Pesos enteros o porcentaje, como texto ("10", "3000"). */
  valor: string
  motivo: string
}

export interface Autorizacion {
  email?: string
  clave?: string
  usuario_id?: string
  pin?: string
}

export interface VentaItem {
  id: string
  producto_id: string
  producto: string
  cantidad: string
  precio_unitario: number
  modificadores: { modificador_id: string; nombre: string; precio: number; costo_total: number }[]
  bruto: number
  descuento: number
  subtotal: number
  costo_total: number
  nota: string | null
}

export interface Venta {
  id: string
  numero: number
  fecha: string
  caja_sesion_id: string
  tipo_servicio: TipoServicio
  cliente_id: string | null
  items: VentaItem[]
  subtotal: number
  descuento_total: number
  descuento_motivo: string | null
  descuento_autorizado_por: string | null
  cortesia: boolean
  total: number
  propina: number
  valor_domicilio: number
  cobrado: number
  cambio: number
  costo_total: number
  pagos: { metodo_pago_id: string; metodo: string; monto: number; recibido: number | null; cambio: number }[]
  estado: 'pagada' | 'anulada'
  cajero: string | null
  motivo_anulacion: string | null
  anulada_en: string | null
}

export interface Cajero {
  id: string
  nombre: string
}
