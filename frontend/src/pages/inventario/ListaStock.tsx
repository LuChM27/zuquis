import { ChevronRight } from 'lucide-react'
import { Celda, FilaTabla, Tabla, Vacio } from '../../components/formulario'
import { Chip } from '../../components/ui'
import { unir } from '../../lib/clases'
import { dec } from '../../lib/decimal'
import type { StockItem } from '../../lib/tipos'
import { cantidadLegible, vencimientoRelativo } from '../../lib/unidades'
import { ESTADOS, FONDO_FILA } from './comun'

interface Props {
  items: StockItem[]
  titulo: string
  seleccionado?: string
  alElegir: (item: StockItem) => void
  hoy: string
  celular: boolean
}

/** Tabla de stock en escritorio; en celular, lista de tarjetas que abren el detalle. */
export function ListaStock({ items, titulo, seleccionado, alElegir, hoy, celular }: Props) {
  if (items.length === 0) {
    return <Vacio>Todavía no hay {titulo.toLowerCase()} activos. Se crean desde Compras o la carta.</Vacio>
  }
  if (celular) {
    return (
      <ul aria-label={titulo} className="-mx-1 flex flex-col gap-2.5">
        {items.map((s) => (
          <li key={s.item_id}>
            <button
              type="button"
              onClick={() => alElegir(s)}
              className={unir(
                'flex w-full items-center gap-3 rounded-control border border-linea px-4 py-3 text-left',
                FONDO_FILA[s.estado] || 'bg-blanco',
              )}
            >
              <span className="min-w-0 flex-1">
                <span className="flex items-start justify-between gap-2">
                  <span className="min-w-0 pt-0.5 font-semibold break-words">{s.nombre}</span>
                  <Chip tono={ESTADOS[s.estado].tono}>{ESTADOS[s.estado].texto}</Chip>
                </span>
                <span className="mt-1 block text-sm text-cafe-medio">
                  Hay {cantidadLegible(s.cantidad, s.unidad)} · mínimo {cantidadLegible(s.minimo, s.unidad)}
                </span>
                <span className="block text-sm text-cafe-suave">
                  Vence: {vencimientoRelativo(s.proximo_vencimiento, hoy)}
                </span>
              </span>
              <ChevronRight aria-hidden className="size-5 shrink-0 text-cafe-suave" />
            </button>
          </li>
        ))}
      </ul>
    )
  }
  return (
    <Tabla
      columnas={[
        { texto: titulo === 'Insumos' ? 'Insumo' : 'Producto' },
        { texto: 'Hay', derecha: true },
        { texto: 'Mínimo', derecha: true },
        { texto: 'Próximo vencimiento' },
        { texto: 'Estado' },
      ]}
    >
      {items.map((s) => (
        <FilaTabla key={s.item_id} seleccionada={s.item_id === seleccionado} alElegir={() => alElegir(s)}>
          <Celda className={unir('text-base font-semibold', FONDO_FILA[s.estado])}>{s.nombre}</Celda>
          <Celda derecha className={unir('text-base whitespace-nowrap', FONDO_FILA[s.estado])}>
            {cantidadLegible(s.cantidad, s.unidad)}
            {dec(s.cantidad_vencida).gt(0) && (
              <span className="block text-sm text-peligro-texto">
                + {cantidadLegible(s.cantidad_vencida, s.unidad)} vencido
              </span>
            )}
          </Celda>
          <Celda derecha className={unir('text-base whitespace-nowrap text-cafe-suave', FONDO_FILA[s.estado])}>
            {cantidadLegible(s.minimo, s.unidad)}
          </Celda>
          <Celda className={unir('pl-6 text-base whitespace-nowrap', FONDO_FILA[s.estado])}>
            {vencimientoRelativo(s.proximo_vencimiento, hoy)}
          </Celda>
          <Celda className={FONDO_FILA[s.estado]}>
            <Chip tono={ESTADOS[s.estado].tono}>{ESTADOS[s.estado].texto}</Chip>
          </Celda>
        </FilaTabla>
      ))}
    </Tabla>
  )
}
