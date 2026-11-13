import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Aviso, Celda, Selector, Vacio } from '../../components/formulario'
import { Boton } from '../../components/ui'
import { api } from '../../lib/api'
import { unir } from '../../lib/clases'
import { dec } from '../../lib/decimal'
import { fechaCorta, hora, pesos } from '../../lib/formato'
import type { Movimiento, Pagina, StockItem, TipoMovimiento } from '../../lib/tipos'
import { cantidadLegible } from '../../lib/unidades'
import { MOVIMIENTOS, rutaItem } from './comun'

const TAMANO = 50

/** Tabla de movimientos. Con `saldo` muestra el saldo acumulado (kardex de un ítem). */
export function TablaMovimientos({
  movimientos,
  unidades,
  conItem,
  conSaldo,
}: {
  movimientos: Movimiento[]
  unidades: Map<string, string>
  conItem?: boolean
  conSaldo?: boolean
}) {
  const columnas = [
    'Fecha',
    ...(conItem ? ['Ítem'] : []),
    'Movimiento',
    'Cantidad',
    'Costo',
    ...(conSaldo ? ['Saldo', 'Saldo $'] : ['Usuario']),
  ]
  const derecha = new Set(['Cantidad', 'Costo', 'Saldo', 'Saldo $'])
  return (
    <div className="-mx-5 overflow-x-auto px-5">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-dorado-claro">
            {columnas.map((c) => (
              <th
                key={c}
                scope="col"
                className={unir(
                  'px-3 pb-3 text-[13px] font-semibold tracking-[0.08em] whitespace-nowrap text-cafe-suave uppercase',
                  derecha.has(c) && 'text-right',
                )}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {movimientos.map((m) => {
            const unidad = unidades.get(m.item_id) ?? ''
            const fecha = new Date(m.fecha)
            const salida = dec(m.cantidad).isNegative()
            return (
              <tr key={m.id} className="border-b border-linea last:border-b-0">
                <Celda className="whitespace-nowrap">
                  {fechaCorta(fecha)}
                  <span className="block text-sm text-cafe-suave">{hora(fecha)}</span>
                </Celda>
                {conItem && <Celda className="font-semibold">{m.item_nombre}</Celda>}
                <Celda className="whitespace-nowrap">{MOVIMIENTOS[m.tipo]}</Celda>
                <Celda derecha className={unir('whitespace-nowrap', salida && 'text-peligro-texto')}>
                  {salida ? '' : '+'}
                  {cantidadLegible(m.cantidad, unidad)}
                </Celda>
                <Celda derecha className={unir('whitespace-nowrap', salida && 'text-peligro-texto')}>
                  {pesos(m.costo_total, { signo: true })}
                </Celda>
                {conSaldo ? (
                  <>
                    <Celda derecha className="whitespace-nowrap">
                      {m.saldo_cantidad !== null ? cantidadLegible(m.saldo_cantidad, unidad) : '—'}
                    </Celda>
                    <Celda derecha className="whitespace-nowrap">
                      {m.saldo_costo !== null ? pesos(m.saldo_costo) : '—'}
                    </Celda>
                  </>
                ) : (
                  <Celda className="text-cafe-medio">{m.usuario ?? '—'}</Celda>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/** Pestaña "Movimientos": todo el libro de inventario, del más reciente al más antiguo. */
export function Movimientos({ stock }: { stock: StockItem[] }) {
  const [pagina, setPagina] = useState(1)
  const [tipo, setTipo] = useState<TipoMovimiento | ''>('')
  const movs = useQuery({
    queryKey: ['inventario', 'movimientos', pagina, tipo],
    queryFn: () =>
      api<Pagina<Movimiento>>(
        `/inventario/movimientos?page=${pagina}&size=${TAMANO}${tipo ? `&tipo=${tipo}` : ''}`,
      ),
    placeholderData: keepPreviousData,
  })
  const unidades = new Map(stock.map((s) => [s.item_id, s.unidad]))
  const total = movs.data?.total ?? 0
  const paginas = Math.max(1, Math.ceil(total / TAMANO))

  return (
    <>
      <Selector
        etiqueta="Tipo de movimiento"
        value={tipo}
        onChange={(e) => {
          setTipo(e.target.value as TipoMovimiento | '')
          setPagina(1)
        }}
        className="mb-4 max-w-xs"
      >
        <option value="">Todos</option>
        {Object.entries(MOVIMIENTOS).map(([valor, texto]) => (
          <option key={valor} value={valor}>
            {texto}
          </option>
        ))}
      </Selector>
      {movs.isError && <Aviso>No pudimos cargar los movimientos. Recarga la página para intentarlo de nuevo.</Aviso>}
      {movs.isSuccess && movs.data.items.length === 0 && <Vacio>No hay movimientos con este filtro.</Vacio>}
      {movs.data && movs.data.items.length > 0 && (
        <>
          <TablaMovimientos movimientos={movs.data.items} unidades={unidades} conItem />
          <Paginador pagina={pagina} paginas={paginas} alCambiar={setPagina} />
        </>
      )}
    </>
  )
}

function Paginador({ pagina, paginas, alCambiar }: { pagina: number; paginas: number; alCambiar: (p: number) => void }) {
  if (paginas <= 1) return null
  return (
    <nav aria-label="Páginas" className="mt-4 flex items-center justify-between gap-3">
      <Boton variante="secundario" disabled={pagina <= 1} onClick={() => alCambiar(pagina - 1)}>
        Anterior
      </Boton>
      <p className="text-sm text-cafe-medio">
        Página {pagina} de {paginas}
      </p>
      <Boton variante="secundario" disabled={pagina >= paginas} onClick={() => alCambiar(pagina + 1)}>
        Siguiente
      </Boton>
    </nav>
  )
}

/** Kardex de un ítem: cada entrada y salida en orden cronológico con su saldo (RF-33). */
export function Kardex({ item }: { item: StockItem }) {
  const [pagina, setPagina] = useState(1)
  const kardex = useQuery({
    queryKey: ['inventario', 'kardex', item.item_id, pagina],
    queryFn: () => api<Pagina<Movimiento>>(`${rutaItem(item)}/kardex?page=${pagina}&size=${TAMANO}`),
    placeholderData: keepPreviousData,
  })
  const unidades = new Map([[item.item_id, item.unidad]])
  const paginas = Math.max(1, Math.ceil((kardex.data?.total ?? 0) / TAMANO))
  return (
    <>
      {kardex.isError && <Aviso>No pudimos cargar el kardex. Intenta de nuevo.</Aviso>}
      {kardex.isSuccess && kardex.data.items.length === 0 && <Vacio>Este ítem todavía no tiene movimientos.</Vacio>}
      {kardex.data && kardex.data.items.length > 0 && (
        <>
          <TablaMovimientos movimientos={kardex.data.items} unidades={unidades} conSaldo />
          <Paginador pagina={pagina} paginas={paginas} alCambiar={setPagina} />
        </>
      )}
    </>
  )
}
