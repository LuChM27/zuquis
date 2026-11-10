/**
 * Piezas básicas recreadas de los mockups (docs/mockups). Medidas en px CSS: los PNG están
 * exportados a 2x sobre un ancho de 1440 px.
 */
import { forwardRef, useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react'

const unir = (...c: (string | false | undefined)[]) => c.filter(Boolean).join(' ')

type Variante = 'primario' | 'secundario'

export function Boton({
  variante = 'primario',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante }) {
  return (
    <button
      type="button"
      {...props}
      className={unir(
        'inline-flex h-12 items-center justify-center gap-2 rounded-control px-[26px] text-[17px] whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-60',
        variante === 'primario' && 'bg-fucsia font-bold text-white hover:bg-fucsia-oscuro',
        variante === 'secundario' &&
          'border border-dorado-claro bg-blanco font-medium text-cafe hover:border-dorado-borde',
        className,
      )}
    />
  )
}

export function Tarjeta({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <section className={unir('rounded-tarjeta border border-dorado-claro bg-blanco p-5', className)}>
      {children}
    </section>
  )
}

/** Título de tarjeta en serif ("Ventas por hora", "Arqueo por método de pago"). */
export function TituloTarjeta({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={unir('font-serif text-[28px] leading-tight font-medium', className)}>{children}</h2>
}

type Tono = 'exito' | 'peligro' | 'aviso' | 'marca' | 'neutro' | 'ejemplo'

const TONOS: Record<Tono, string> = {
  exito: 'bg-exito-fondo text-exito-texto',
  peligro: 'bg-peligro-fondo text-peligro-texto',
  aviso: 'bg-aviso-fondo text-aviso-texto',
  marca: 'bg-rosa-suave text-fucsia-oscuro',
  neutro: 'bg-pista text-cafe',
  ejemplo: 'bg-arena text-dorado-texto font-medium',
}

/** Chip de estado: "Bien", "Bajo el mínimo", "Por vencer", "Listo", "Pendiente". */
export function Chip({ tono = 'neutro', children }: { tono?: Tono; children: ReactNode }) {
  return (
    <span
      className={unir(
        'inline-flex h-7 items-center rounded-full px-3 text-sm font-semibold whitespace-nowrap',
        TONOS[tono],
      )}
    >
      {children}
    </span>
  )
}

/** Línea de contexto + título grande en serif + acciones a la derecha. */
export function EncabezadoPagina({
  contexto,
  titulo,
  acciones,
}: {
  contexto?: ReactNode
  titulo: ReactNode
  acciones?: ReactNode
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4 lg:mb-[22px]">
      <div className="min-w-0">
        {contexto && <p className="text-sm text-cafe-suave lg:text-[15px]">{contexto}</p>}
        <h1 className="mt-1 font-serif text-[40px] leading-[1.1] font-medium lg:text-[52px]">{titulo}</h1>
      </div>
      {acciones && <div className="flex flex-wrap items-center gap-3">{acciones}</div>}
    </header>
  )
}

interface PropsCampo extends InputHTMLAttributes<HTMLInputElement> {
  etiqueta: string
  error?: string
  extra?: ReactNode
}

/** Campo con etiqueta visible siempre; el error aparece debajo y se anuncia. */
export const Campo = forwardRef<HTMLInputElement, PropsCampo>(function Campo(
  { etiqueta, error, extra, className, ...props },
  ref,
) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-semibold">
        {etiqueta}
      </label>
      <div className="relative">
        <input
          ref={ref}
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          {...props}
          className={unir(
            'h-12 w-full rounded-control border bg-blanco px-4 text-base placeholder:text-cafe-suave/70 focus:border-dorado-borde focus:outline-none',
            error ? 'border-peligro' : 'border-dorado-claro',
            extra ? 'pr-12' : undefined,
          )}
        />
        {extra && <div className="absolute inset-y-0 right-1 flex items-center">{extra}</div>}
      </div>
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-sm text-peligro-texto">
          {error}
        </p>
      )}
    </div>
  )
})
