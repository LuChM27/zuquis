/**
 * Cliente de reportes (fase 4): tipos de las respuestas, atajos de fecha y consultas.
 * Los montos llegan como enteros; porcentajes y cantidades como texto (nunca float).
 */
import { useQuery } from '@tanstack/react-query'
import { api, apiBlob } from './api'
import { hoyIso } from './unidades'

export type TipoReporte =
  | 'ventas'
  | 'gastos'
  | 'flujo-caja'
  | 'utilidad-productos'
  | 'inventario-valorizado'
  | 'mermas'
  | 'propinas'
  | 'domicilios'
  | 'descuentos-cortesias'
  | 'ingresos-cancelacion'
  | 'cierres'
  | 'puc'

export const NOMBRES_REPORTE: Record<TipoReporte, string> = {
  ventas: 'Ventas',
  gastos: 'Gastos',
  'flujo-caja': 'Flujo de caja',
  'utilidad-productos': 'Utilidad por producto',
  'inventario-valorizado': 'Inventario valorizado',
  mermas: 'Mermas',
  propinas: 'Propinas',
  domicilios: 'Domicilios',
  'descuentos-cortesias': 'Descuentos y cortesías',
  'ingresos-cancelacion': 'Ingresos por cancelación',
  cierres: 'Cierres de caja',
  puc: 'Movimientos PUC (contador)',
}

// Igual que ACCESO en backend/app/modules/reportes/router.py (el backend sigue mandando).
const ACCESO: Record<TipoReporte, string[]> = {
  ventas: ['reportes.ver', 'reportes.ver_caja_propia'],
  gastos: ['reportes.ver'],
  'flujo-caja': ['reportes.ver'],
  'utilidad-productos': ['reportes.ver'],
  'inventario-valorizado': ['reportes.ver', 'reportes.ver_inventario'],
  mermas: ['reportes.ver', 'reportes.ver_inventario'],
  propinas: ['reportes.ver'],
  domicilios: ['reportes.ver'],
  'descuentos-cortesias': ['reportes.ver'],
  'ingresos-cancelacion': ['reportes.ver'],
  cierres: ['reportes.ver'],
  puc: ['reportes.ver'],
}

export function TIPOS_VISIBLES(permisos: readonly string[]): TipoReporte[] {
  return (Object.keys(ACCESO) as TipoReporte[]).filter((t) => ACCESO[t].some((p) => permisos.includes(p)))
}

export type TipoColumna = 'texto' | 'pesos' | 'cantidad' | 'porcentaje' | 'fecha' | 'entero'
export interface Columna {
  clave: string
  titulo: string
  tipo: TipoColumna
}
export type Fila = Record<string, string | number | boolean | null>
export interface Seccion {
  titulo: string
  columnas: Columna[]
  filas: Fila[]
  totales: Record<string, number> | null
}
export interface Reporte {
  tipo: TipoReporte
  titulo: string
  sede: string
  desde: string
  hasta: string
  generado_en: string
  secciones: Seccion[]
}

export interface FilaVentas {
  clave: string
  etiqueta: string
  ventas: number
  costo: number
  unidades: string
  n: number
}
export interface Alerta {
  tipo: 'bajo_minimo' | 'por_vencer' | 'vencido' | 'faltante' | 'verificacion'
  titulo: string
  detalle: string
}
export interface EncargoHoy {
  id: string
  numero: number
  descripcion: string
  cliente: string
  hora: string
  saldo: number
  estado: string
}
export interface Dashboard {
  fecha: string
  caja_abierta_desde: string | null
  datos_ejemplo: boolean
  ventas: number
  n_ventas: number
  gastos: number
  n_gastos: number
  ganancia: number
  ticket_promedio: number
  por_hora: FilaVentas[]
  por_metodo: FilaVentas[]
  porcentaje_metodo: Record<string, string>
  mas_vendidos: FilaVentas[]
  encargos_hoy: EncargoHoy[]
  alertas: Alerta[]
}

export type Grupo = 'ganancia' | 'ventas' | 'productos' | 'gastos' | 'encargos' | 'cajeros'
export interface DatosGrupo {
  ganancia: {
    cascada: Record<'ventas' | 'costo_insumos' | 'regalado' | 'gastos' | 'mermas' | 'ingresos_cancelacion' | 'utilidad', number>
    costo_pct: { semana: string; ventas: number; costo: number; pct: string }[]
    flujo: { dia: string; entra_negocio: number; entra_dueno: number; sale: number }[]
  }
  ventas: {
    dia_a_dia: { dia: string; ventas: number }[]
    anterior: { dia: string; ventas: number }[]
    calor: { dow: number; hora: number; ventas: number }[]
    categorias: { categoria: string; ventas: number; pct: string }[]
  }
  productos: {
    producido_vendido: { producto: string; producido: string; vendido: string }[]
    mas_vendidos?: { producto: string; unidades: string; ventas: number }[]
    menos_vendidos?: { producto: string; unidades: string | number }[]
  }
  gastos: {
    mermas: { por_motivo: { motivo: string; costo: number }[]; por_item: { item: string; costo: number }[] }
    por_categoria_mes?: { mes: string; categoria: string; monto: number }[]
    por_pagar?: {
      con_fecha: { vencidas: number; esta_semana: number; proximas: number }
      sin_fecha: { d0_15: number; d16_30: number; d30_mas: number }
    }
  }
  encargos: {
    por_semana: { semana: string; entregados: number; cancelados: number }[]
    abonos_sin_entregar: number
    clientes_top: { cliente: string; encargos: number; total: number }[]
  }
  cajeros: {
    por_cajero: { cajero: string; vendido: number; descuentos: number; cortesias: number; diferencia_cierres: number }[]
  }
}

export interface Rango {
  desde: string
  hasta: string
  sedeId?: string
}
export type Atajo = 'hoy' | 'ayer' | 'semana' | 'mes'

function sumarDias(iso: string, dias: number): string {
  const d = new Date(`${iso}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + dias)
  return d.toISOString().slice(0, 10)
}

/** Rangos rápidos en fechas de Bogotá; la semana empieza el lunes. */
export function atajo(nombre: Atajo, ahora: Date = new Date()): Rango {
  const hoy = hoyIso(ahora)
  if (nombre === 'hoy') return { desde: hoy, hasta: hoy }
  if (nombre === 'ayer') {
    const ayer = sumarDias(hoy, -1)
    return { desde: ayer, hasta: ayer }
  }
  if (nombre === 'mes') return { desde: `${hoy.slice(0, 8)}01`, hasta: hoy }
  const dow = new Date(`${hoy}T12:00:00Z`).getUTCDay() || 7 // lunes = 1 … domingo = 7
  return { desde: sumarDias(hoy, 1 - dow), hasta: hoy }
}

function parametros(r: Rango, extra: Record<string, string> = {}): string {
  const p = new URLSearchParams({ desde: r.desde, hasta: r.hasta, ...extra })
  if (r.sedeId) p.set('sede_id', r.sedeId)
  return p.toString()
}

export function useReporte(tipo: TipoReporte | undefined, r: Rango) {
  return useQuery({
    queryKey: ['reportes', tipo, r],
    queryFn: () => api<Reporte>(`/reportes/${tipo}?${parametros(r)}`),
    enabled: !!tipo,
  })
}

export function useGrupoGraficos<G extends Grupo>(grupo: G, r: Rango, activo: boolean) {
  return useQuery({
    queryKey: ['reportes', 'graficos', grupo, r],
    queryFn: () => api<DatosGrupo[G]>(`/reportes/graficos?${parametros(r, { grupo })}`),
    enabled: activo,
  })
}

export function useDashboard() {
  return useQuery({ queryKey: ['reportes', 'dashboard'], queryFn: () => api<Dashboard>('/reportes/dashboard'), refetchInterval: 60_000 })
}

/** Descarga el reporte en Excel o PDF con el mismo nombre que da el backend. */
export async function exportar(tipo: TipoReporte, r: Rango, formato: 'xlsx' | 'pdf'): Promise<void> {
  const blob = await apiBlob(`/reportes/${tipo}?${parametros(r, { formato })}`)
  const url = URL.createObjectURL(blob)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = `zuquis-${tipo}-${r.desde}-${r.hasta}.${formato}`
  enlace.click()
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
