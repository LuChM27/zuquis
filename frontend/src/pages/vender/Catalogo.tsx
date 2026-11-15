import { Search } from 'lucide-react'
import { useMemo } from 'react'
import { coincide } from '../../lib/buscar'
import { unir } from '../../lib/clases'
import { pesos } from '../../lib/formato'
import type { Categoria, Producto } from '../../lib/tipos'
import { IconoCategoria } from '../carta/comun'
import { estadoProducto } from './logica'

/** Fondos del ícono de las tarjetas (mockup): rosas, beige y crema según la categoría. */
const FONDOS = ['bg-rosa-suave', 'bg-[#fde2e8]', 'bg-[#f5ebe2]', 'bg-[#fcf0db]', 'bg-[#f3ede3]']

const TONO_ESTADO = { normal: 'text-cafe-medio', bien: 'text-exito-texto', bajo: 'text-peligro-texto' }

export function Catalogo({
  categorias,
  productos,
  busqueda,
  alBuscar,
  categoria,
  alElegirCategoria,
  enCarrito,
  alAgregar,
  acciones,
}: {
  categorias: Categoria[]
  productos: Producto[]
  busqueda: string
  alBuscar: (v: string) => void
  categoria: string | null
  alElegirCategoria: (id: string | null) => void
  /** Unidades de cada producto en el carrito (contador de la tarjeta en celular). */
  enCarrito: Map<string, number>
  alAgregar: (p: Producto) => void
  acciones?: React.ReactNode
}) {
  const indice = useMemo(() => new Map(categorias.map((c, i) => [c.id, i])), [categorias])
  const iconos = useMemo(() => new Map(categorias.map((c) => [c.id, c.icono])), [categorias])
  // Con algo escrito se busca en toda la carta, sin importar la categoría elegida.
  const visibles = busqueda.trim()
    ? productos.filter((p) => coincide(p.nombre, busqueda))
    : productos.filter((p) => categoria === null || p.categoria_id === categoria)
  const conProductos = categorias.filter((c) => productos.some((p) => p.categoria_id === c.id))

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 lg:flex-nowrap">
        <h1 className="hidden font-serif text-[52px] leading-[1.1] font-medium lg:block">Vender</h1>
        <div className="flex w-full items-center gap-3 lg:w-[370px]">
          <label className="flex h-[54px] min-w-0 flex-1 items-center gap-3 rounded-control border border-dorado-claro bg-blanco px-4 focus-within:border-dorado-borde">
            <Search aria-hidden className="size-5 shrink-0 text-cafe-medio" strokeWidth={1.8} />
            <span className="sr-only">Buscar producto</span>
            <input
              type="search"
              value={busqueda}
              onChange={(e) => alBuscar(e.target.value)}
              placeholder="Buscar producto…"
              className="min-w-0 flex-1 bg-transparent text-[17px] placeholder:text-cafe-suave/80 focus:outline-none"
            />
          </label>
          {acciones}
        </div>
      </div>

      <div
        role="tablist"
        aria-label="Categorías"
        className="-mx-4 mt-4 flex gap-2.5 overflow-x-auto px-4 pb-1 lg:mx-0 lg:mt-5 lg:flex-wrap lg:px-0"
      >
        {[{ id: null, nombre: 'Todo' }, ...conProductos].map((c) => {
          const activa = !busqueda.trim() && categoria === c.id
          return (
            <button
              key={c.id ?? 'todo'}
              type="button"
              role="tab"
              aria-selected={activa}
              onClick={() => {
                alBuscar('')
                alElegirCategoria(c.id)
              }}
              className={unir(
                'h-[46px] shrink-0 rounded-full border px-5 text-[17px] whitespace-nowrap transition-colors',
                activa ? 'border-fucsia bg-fucsia font-semibold text-white' : 'border-dorado-claro bg-blanco hover:border-dorado-borde',
              )}
            >
              {c.nombre}
            </button>
          )
        })}
      </div>

      {visibles.length === 0 ? (
        <p className="mt-10 text-center text-cafe-medio">
          {busqueda.trim() ? `Ningún producto coincide con "${busqueda.trim()}".` : 'No hay productos en esta categoría.'}
        </p>
      ) : (
        <ul className="mt-6 grid grid-cols-2 gap-3.5 lg:mt-7 lg:gap-4 xl:grid-cols-4 lg:grid-cols-3">
          {visibles.map((p) => {
            const estado = estadoProducto(p)
            const cantidad = enCarrito.get(p.id) ?? 0
            return (
              <li key={p.id}>
                <button
                  type="button"
                  disabled={!estado.vendible}
                  onClick={() => alAgregar(p)}
                  aria-label={`${p.nombre}, ${pesos(p.precio)}, ${estado.texto}${cantidad ? `, ${cantidad} en la venta` : ''}`}
                  className={unir(
                    'flex h-full w-full flex-col rounded-tarjeta border bg-blanco p-3 text-left transition-[border-color,transform] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-55 lg:p-3.5',
                    cantidad ? 'border-fucsia lg:border-dorado-claro' : 'border-dorado-claro hover:border-dorado-borde',
                  )}
                >
                  <span
                    aria-hidden
                    className={unir(
                      'hidden h-[78px] w-full place-items-center rounded-[12px] text-fucsia-oscuro lg:grid',
                      FONDOS[(indice.get(p.categoria_id) ?? 0) % FONDOS.length],
                    )}
                  >
                    <IconoCategoria icono={iconos.get(p.categoria_id) ?? null} className="size-7" />
                  </span>
                  <span className="mt-0 text-[17px] leading-snug font-medium [overflow-wrap:anywhere] lg:mt-3.5">{p.nombre}</span>
                  <span className={unir('mt-1 text-[15px] font-medium lg:hidden', TONO_ESTADO[estado.tono])}>{estado.texto}</span>
                  <span className="mt-auto flex flex-wrap items-end justify-between gap-x-2 gap-y-1 pt-4">
                    <span className="text-xl font-bold">{pesos(p.precio)}</span>
                    <span className={unir('hidden text-sm font-medium whitespace-nowrap lg:inline', TONO_ESTADO[estado.tono])}>{estado.texto}</span>
                    {cantidad > 0 && (
                      <span
                        aria-hidden
                        className="grid size-[34px] shrink-0 place-items-center rounded-full bg-fucsia text-base font-bold text-white lg:hidden"
                      >
                        {cantidad}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
