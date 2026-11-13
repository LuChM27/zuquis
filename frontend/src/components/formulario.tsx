/**
 * Controles de formulario y piezas de lista/detalle, con el mismo lenguaje visual de los
 * mockups (pestañas en píldora de Inventario, tabla con encabezados en versalitas, panel de
 * detalle con borde dorado).
 */
import { CircleAlert } from 'lucide-react'
import { useId, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'

import { unir } from '../lib/clases'

/** Pestañas en píldora: la activa en fucsia ("Insumos (42)" en el mockup de inventario). */
export function Pildoras<T extends string>({
  opciones,
  valor,
  alCambiar,
  etiqueta,
}: {
  opciones: { valor: T; texto: string }[]
  valor: T
  alCambiar: (v: T) => void
  etiqueta: string
}) {
  return (
    <div role="tablist" aria-label={etiqueta} className="-mx-4 flex gap-2.5 overflow-x-auto px-4 pb-1 lg:mx-0 lg:flex-wrap lg:px-0">
      {opciones.map((o) => {
        const activa = o.valor === valor
        return (
          <button
            key={o.valor}
            type="button"
            role="tab"
            aria-selected={activa}
            onClick={() => alCambiar(o.valor)}
            className={unir(
              'h-[46px] shrink-0 rounded-full border px-5 text-base whitespace-nowrap transition-colors',
              activa
                ? 'border-fucsia bg-fucsia font-semibold text-white'
                : 'border-dorado-claro bg-blanco hover:border-dorado-borde',
            )}
          >
            {o.texto}
          </button>
        )
      })}
    </div>
  )
}

/** Tabla con encabezados en versalitas y filas separadas por línea, como en los mockups. */
export function Tabla({ columnas, children }: { columnas: { texto: string; derecha?: boolean; ocultarMovil?: boolean }[]; children: ReactNode }) {
  return (
    <div className="-mx-5 overflow-x-auto px-5">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-dorado-claro">
            {columnas.map((c) => (
              <th
                key={c.texto}
                scope="col"
                className={unir(
                  'px-3 pb-3 text-[13px] font-semibold tracking-[0.08em] whitespace-nowrap text-cafe-suave uppercase',
                  c.derecha && 'text-right',
                  c.ocultarMovil && 'hidden md:table-cell',
                )}
              >
                {c.texto}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

/** Fila seleccionable: abre el detalle con clic o Enter. */
export function FilaTabla({
  seleccionada,
  alElegir,
  children,
}: {
  seleccionada?: boolean
  alElegir: () => void
  children: ReactNode
}) {
  return (
    <tr
      tabIndex={0}
      aria-selected={seleccionada}
      onClick={alElegir}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          alElegir()
        }
      }}
      className={unir(
        'cursor-pointer border-b border-linea transition-colors last:border-b-0 focus-visible:outline-offset-[-2px]',
        seleccionada ? 'bg-rosa-suave/60' : 'hover:bg-crema',
      )}
    >
      {children}
    </tr>
  )
}

export function Celda({
  children,
  derecha,
  ocultarMovil,
  className,
}: {
  children: ReactNode
  derecha?: boolean
  ocultarMovil?: boolean
  className?: string
}) {
  return (
    <td
      className={unir(
        'h-[60px] px-3 py-2 align-middle',
        derecha && 'text-right',
        ocultarMovil && 'hidden md:table-cell',
        className,
      )}
    >
      {children}
    </td>
  )
}

/** Panel lateral de detalle ("DETALLE / Harina de trigo" en el mockup de inventario). */
export function PanelDetalle({
  rotulo,
  titulo,
  subtitulo,
  children,
}: {
  rotulo: string
  titulo: ReactNode
  subtitulo?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="rounded-tarjeta border-[1.5px] border-dorado-borde bg-blanco p-5">
      <p className="text-[13px] font-semibold tracking-[0.12em] text-dorado-texto uppercase">{rotulo}</p>
      <h2 className="mt-1 font-serif text-[32px] leading-[1.1] font-medium break-words">{titulo}</h2>
      {subtitulo && <p className="mt-1.5 text-cafe-medio">{subtitulo}</p>}
      <div className="mt-5">{children}</div>
    </section>
  )
}

/** Diseño lista + detalle de los mockups; en celular el detalle queda debajo. */
export function ListaDetalle({
  lista,
  detalle,
  angosto,
}: {
  lista: ReactNode
  detalle: ReactNode
  /** Panel de 320 px (inventario) en vez de 380 px (formularios de configuración). */
  angosto?: boolean
}) {
  return (
    <div
      className={unir(
        'grid items-start gap-4',
        angosto ? 'lg:grid-cols-[minmax(0,1fr)_320px]' : 'lg:grid-cols-[minmax(0,1fr)_380px]',
      )}
    >
      {lista}
      <div id="panel-detalle" className="scroll-mt-24">
        {detalle}
      </div>
    </div>
  )
}

export function Aviso({ tono = 'peligro', children }: { tono?: 'peligro' | 'aviso'; children: ReactNode }) {
  return (
    <p
      role={tono === 'peligro' ? 'alert' : 'status'}
      className={unir(
        'flex gap-2.5 rounded-control p-3.5 text-sm',
        tono === 'peligro' ? 'bg-peligro-fondo text-peligro-texto' : 'bg-aviso-fondo text-cafe-medio',
      )}
    >
      <CircleAlert
        aria-hidden
        className={unir('mt-px size-[18px] shrink-0', tono === 'aviso' && 'text-aviso')}
      />
      <span>{children}</span>
    </p>
  )
}

/** Interruptor accesible (role="switch"). */
export function Interruptor({
  etiqueta,
  ayuda,
  activo,
  alCambiar,
  deshabilitado,
}: {
  etiqueta: string
  ayuda?: string
  activo: boolean
  alCambiar: (v: boolean) => void
  deshabilitado?: boolean
}) {
  const id = useId()
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p id={id} className="text-sm font-semibold">
          {etiqueta}
        </p>
        {ayuda && <p className="mt-0.5 text-sm text-cafe-suave">{ayuda}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={activo}
        aria-labelledby={id}
        disabled={deshabilitado}
        onClick={() => alCambiar(!activo)}
        className={unir(
          'relative mt-0.5 h-7 w-12 shrink-0 rounded-full transition-colors disabled:opacity-50',
          activo ? 'bg-exito' : 'bg-pista ring-1 ring-dorado-claro',
        )}
      >
        <span
          className={unir(
            'absolute top-1 left-1 size-5 rounded-full bg-white shadow-sm transition-transform',
            activo && 'translate-x-5',
          )}
        />
      </button>
    </div>
  )
}

export function Casilla({
  etiqueta,
  ayuda,
  marcada,
  alCambiar,
}: {
  etiqueta: string
  ayuda?: string
  marcada: boolean
  alCambiar: (v: boolean) => void
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 py-1.5">
      <input
        type="checkbox"
        checked={marcada}
        onChange={(e) => alCambiar(e.target.checked)}
        className="mt-0.5 size-[18px] shrink-0 accent-fucsia"
      />
      <span>
        <span className="block text-[15px]">{etiqueta}</span>
        {ayuda && <span className="block text-xs text-cafe-suave">{ayuda}</span>}
      </span>
    </label>
  )
}

export function Selector({
  etiqueta,
  children,
  className,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { etiqueta: string }) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-semibold">
        {etiqueta}
      </label>
      <select
        id={id}
        {...props}
        className="h-12 w-full rounded-control border border-dorado-claro bg-blanco px-3.5 text-base focus:border-dorado-borde focus:outline-none"
      >
        {children}
      </select>
    </div>
  )
}

export function AreaTexto({
  etiqueta,
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { etiqueta: string }) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-semibold">
        {etiqueta}
      </label>
      <textarea
        id={id}
        rows={2}
        {...props}
        className="w-full rounded-control border border-dorado-claro bg-crema px-4 py-3 text-base focus:border-dorado-borde focus:outline-none"
      />
    </div>
  )
}

/** Estado vacío de una lista. */
export function Vacio({ children }: { children: ReactNode }) {
  return <p className="py-10 text-center text-cafe-medio">{children}</p>
}
