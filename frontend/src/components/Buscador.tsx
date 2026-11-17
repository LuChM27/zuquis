/**
 * Campo para elegir entre muchas opciones escribiendo: la lista se filtra mientras se escribe
 * (sin importar tildes ni mayúsculas) y también se puede recorrer completa. Patrón "combobox"
 * de WAI-ARIA: flechas para moverse, Enter para elegir, Esc para cerrar.
 *
 * Regla del proyecto: toda lista larga para elegir (insumos, productos, proveedores, clientes…)
 * usa este campo en vez de un <select>.
 */
import { Check, ChevronDown } from 'lucide-react'
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { coincide } from '../lib/buscar'
import { unir } from '../lib/clases'

export interface OpcionBuscador {
  valor: string
  texto: string
  /** Texto pequeño a la derecha: unidad, precio, "sin receta"… */
  detalle?: string
  /** Texto que también se busca aunque no se muestre (el teléfono sin espacios, un código). */
  busqueda?: string
  deshabilitada?: boolean
}

const coincideOpcion = (o: OpcionBuscador, q: string) => coincide(o.busqueda ? `${o.texto} ${o.busqueda}` : o.texto, q)

export function Buscador({
  etiqueta,
  opciones,
  valor,
  alCambiar,
  placeholder = 'Escribe para buscar',
  error,
  ocultarEtiqueta,
  deshabilitado,
  className,
}: {
  etiqueta: string
  opciones: OpcionBuscador[]
  valor: string
  alCambiar: (valor: string) => void
  placeholder?: string
  error?: string
  /** La etiqueta queda solo para lectores de pantalla (filas de una tabla con encabezado). */
  ocultarEtiqueta?: boolean
  deshabilitado?: boolean
  className?: string
}) {
  const id = useId()
  const elegida = opciones.find((o) => o.valor === valor)
  const [abierto, setAbierto] = useState(false)
  const [consulta, setConsulta] = useState<string | null>(null)
  const [activa, setActiva] = useState(0)
  const caja = useRef<HTMLDivElement>(null)
  const lista = useRef<HTMLUListElement>(null)

  // Mientras no se escribe, el campo muestra la opción elegida.
  const texto = consulta ?? elegida?.texto ?? ''
  const filtradas = consulta ? opciones.filter((o) => coincideOpcion(o, consulta)) : opciones

  function cerrar() {
    setAbierto(false)
    setConsulta(null)
  }

  function elegir(o: OpcionBuscador | undefined) {
    if (!o || o.deshabilitada) return
    alCambiar(o.valor)
    cerrar()
  }

  function mover(paso: 1 | -1) {
    if (filtradas.length === 0) return
    let i = activa
    for (let n = 0; n < filtradas.length; n++) {
      i = (i + paso + filtradas.length) % filtradas.length
      if (!filtradas[i].deshabilitada) break
    }
    setActiva(i)
  }

  function alTeclear(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (!abierto) setAbierto(true)
      else mover(e.key === 'ArrowDown' ? 1 : -1)
    } else if (e.key === 'Enter' && abierto) {
      e.preventDefault()
      elegir(filtradas[activa])
    } else if (e.key === 'Escape' && abierto) {
      e.preventDefault()
      cerrar()
    }
  }

  // Al hacer clic fuera se cierra y se vuelve a la opción elegida.
  useEffect(() => {
    if (!abierto) return
    const fuera = (e: PointerEvent) => {
      if (!caja.current?.contains(e.target as Node)) cerrar()
    }
    document.addEventListener('pointerdown', fuera)
    return () => document.removeEventListener('pointerdown', fuera)
  }, [abierto])

  // La opción activa siempre queda a la vista dentro de la lista.
  useEffect(() => {
    lista.current?.querySelector<HTMLElement>(`[data-indice="${activa}"]`)?.scrollIntoView?.({ block: 'nearest' })
  }, [activa])

  const primeraHabilitada = (l: OpcionBuscador[]) => Math.max(0, l.findIndex((o) => !o.deshabilitada))

  return (
    <div ref={caja} className={unir('relative', className)}>
      <label htmlFor={id} className={ocultarEtiqueta ? 'sr-only' : 'mb-1.5 block text-sm font-semibold'}>
        {etiqueta}
      </label>
      <div className="relative">
        <input
          id={id}
          role="combobox"
          aria-expanded={abierto}
          aria-controls={`${id}-lista`}
          aria-autocomplete="list"
          aria-activedescendant={abierto && filtradas[activa] ? `${id}-${activa}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          autoComplete="off"
          disabled={deshabilitado}
          placeholder={elegida ? undefined : placeholder}
          value={texto}
          onFocus={(e) => {
            e.target.select()
            setActiva(primeraHabilitada(opciones))
            setAbierto(true)
          }}
          onClick={() => setAbierto(true)}
          onChange={(e) => {
            const q = e.target.value
            setConsulta(q)
            setAbierto(true)
            setActiva(primeraHabilitada(q ? opciones.filter((o) => coincideOpcion(o, q)) : opciones))
          }}
          onKeyDown={alTeclear}
          className={unir(
            'h-12 w-full rounded-control border bg-blanco pr-10 pl-3.5 text-base placeholder:text-cafe-suave/70 focus:border-dorado-borde focus:outline-none disabled:opacity-60',
            error ? 'border-peligro' : 'border-dorado-claro',
          )}
        />
        <ChevronDown aria-hidden className="pointer-events-none absolute top-1/2 right-3 size-[18px] -translate-y-1/2 text-cafe-suave" />
      </div>
      {abierto && (
        <ul
          ref={lista}
          id={`${id}-lista`}
          role="listbox"
          aria-label={etiqueta}
          className="absolute z-30 mt-1 max-h-72 w-full min-w-56 overflow-y-auto rounded-control border border-dorado-claro bg-blanco py-1 shadow-[0_8px_24px_rgb(74_52_40/0.12)]"
        >
          {filtradas.length === 0 && (
            <li className="px-3.5 py-3 text-sm text-cafe-medio">Nada coincide con «{consulta}».</li>
          )}
          {filtradas.map((o, i) => (
            <li
              key={o.valor}
              id={`${id}-${i}`}
              data-indice={i}
              role="option"
              aria-selected={o.valor === valor}
              aria-disabled={o.deshabilitada || undefined}
              // pointerdown en vez de click: elige antes de que el campo pierda el foco.
              onPointerDown={(e) => {
                e.preventDefault()
                elegir(o)
              }}
              onClick={() => elegir(o)}
              onPointerMove={() => !o.deshabilitada && setActiva(i)}
              className={unir(
                'flex min-h-11 cursor-pointer items-center gap-2 px-3.5 py-2',
                i === activa && !o.deshabilitada && 'bg-rosa-suave/60',
                o.deshabilitada && 'cursor-not-allowed opacity-50',
              )}
            >
              <span className="min-w-0 flex-1">{o.texto}</span>
              {o.detalle && <span className="shrink-0 text-sm text-cafe-suave">{o.detalle}</span>}
              {o.valor === valor && <Check aria-hidden className="size-4 shrink-0 text-fucsia" />}
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-sm text-peligro-texto">
          {error}
        </p>
      )}
    </div>
  )
}

/** Caja de texto para filtrar una lista o tabla que ya está en pantalla. */
export function FiltroLista({
  etiqueta,
  valor,
  alCambiar,
  className,
}: {
  etiqueta: string
  valor: string
  alCambiar: (v: string) => void
  className?: string
}) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id} className="sr-only">
        {etiqueta}
      </label>
      <input
        id={id}
        type="search"
        value={valor}
        placeholder={etiqueta}
        onChange={(e) => alCambiar(e.target.value)}
        className="h-11 w-full rounded-control border border-dorado-claro bg-blanco px-3.5 text-base placeholder:text-cafe-suave/80 focus:border-dorado-borde focus:outline-none"
      />
    </div>
  )
}

/**
 * Lista de casillas para marcar varias opciones (insumos de un proveedor, productos de una
 * adición). Con más de 8 opciones aparece arriba una caja para filtrarlas escribiendo; las
 * marcadas se cuentan aunque queden ocultas por el filtro.
 */
export function CasillasConBusqueda({
  etiqueta,
  opciones,
  marcadas,
  alCambiar,
}: {
  etiqueta: string
  opciones: { valor: string; texto: string }[]
  marcadas: string[]
  alCambiar: (marcadas: string[]) => void
}) {
  const [busqueda, setBusqueda] = useState('')
  const visibles = opciones.filter((o) => coincide(o.texto, busqueda))
  return (
    <fieldset>
      <legend className="mb-1 text-sm font-semibold">
        {etiqueta}
        {marcadas.length > 0 && <span className="font-normal text-cafe-suave"> · {marcadas.length} marcados</span>}
      </legend>
      {opciones.length > 8 && (
        <FiltroLista etiqueta={`Buscar en ${etiqueta.toLowerCase()}`} valor={busqueda} alCambiar={setBusqueda} className="mb-2" />
      )}
      <div className="max-h-64 overflow-y-auto rounded-control border border-linea px-3 py-1">
        {visibles.length === 0 && <p className="py-2 text-sm text-cafe-medio">Nada coincide.</p>}
        {visibles.map((o) => (
          <label key={o.valor} className="flex cursor-pointer items-start gap-3 py-1.5">
            <input
              type="checkbox"
              checked={marcadas.includes(o.valor)}
              onChange={(e) => alCambiar(e.target.checked ? [...marcadas, o.valor] : marcadas.filter((x) => x !== o.valor))}
              className="mt-0.5 size-[18px] shrink-0 accent-fucsia"
            />
            <span className="text-[15px]">{o.texto}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
