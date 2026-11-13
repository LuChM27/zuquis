import {
  BookOpen,
  Box,
  Calendar,
  ChartColumn,
  House,
  ReceiptText,
  ShoppingCart,
  SlidersHorizontal,
  Truck,
  Wallet,
  type LucideIcon,
} from 'lucide-react'

export interface Seccion {
  ruta: string
  nombre: string
  icono: LucideIcon
  /** Se muestra si el usuario tiene al menos uno de estos permisos. */
  permisos: string[]
  /** Fase del plan en la que se construye la pantalla. */
  fase: number
}

/** Mismo orden e íconos que la barra lateral de los mockups. */
export const SECCIONES: Seccion[] = [
  { ruta: '/', nombre: 'Inicio', icono: House, permisos: ['reportes.ver'], fase: 4 },
  { ruta: '/vender', nombre: 'Vender', icono: ShoppingCart, permisos: ['ventas.crear'], fase: 2 },
  {
    ruta: '/caja',
    nombre: 'Caja',
    icono: Wallet,
    permisos: ['caja.abrir', 'caja.cerrar', 'caja.movimientos'],
    fase: 2,
  },
  { ruta: '/encargos', nombre: 'Encargos', icono: Calendar, permisos: ['encargos.crear'], fase: 3 },
  { ruta: '/inventario', nombre: 'Inventario', icono: Box, permisos: ['inventario.ver'], fase: 1 },
  // La carta no está en la barra de los mockups; se agregó aquí (decisión del 13/11/2026).
  {
    ruta: '/carta',
    nombre: 'Carta',
    icono: BookOpen,
    permisos: ['carta.editar', 'recetas.editar', 'insumos.gestionar'],
    fase: 1,
  },
  // Compras incluye proveedores, cuentas por pagar y la producción.
  {
    ruta: '/compras',
    nombre: 'Compras',
    icono: Truck,
    permisos: ['compras.crear', 'proveedores.gestionar', 'produccion.crear'],
    fase: 1,
  },
  {
    ruta: '/gastos',
    nombre: 'Gastos',
    icono: ReceiptText,
    permisos: ['gastos.crear', 'gastos.crear_caja'],
    fase: 2,
  },
  {
    ruta: '/reportes',
    nombre: 'Reportes',
    icono: ChartColumn,
    permisos: ['reportes.ver', 'reportes.ver_caja_propia', 'reportes.ver_inventario'],
    fase: 4,
  },
  {
    ruta: '/configuracion',
    nombre: 'Configuración',
    icono: SlidersHorizontal,
    permisos: ['config.editar', 'usuarios.gestionar'],
    fase: 0,
  },
]

export function seccionesVisibles(permisos: string[]): Seccion[] {
  return SECCIONES.filter((s) => s.permisos.some((p) => permisos.includes(p)))
}
