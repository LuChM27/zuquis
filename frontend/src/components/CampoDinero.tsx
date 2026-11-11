import { useId } from 'react'
import { unir } from '../lib/clases'
import { leerPesos } from '../lib/formato'

const miles = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0, useGrouping: 'always' })

/**
 * Campo de pesos enteros como el "Contado" del mockup de cierre de caja: "$" gris a la
 * izquierda, cifra en negrita a la derecha con separador de miles mientras se escribe.
 */
export function CampoDinero({
  etiqueta,
  valor,
  alCambiar,
  error,
  ocultarEtiqueta,
  className,
}: {
  etiqueta: string
  valor: number | null
  alCambiar: (v: number | null) => void
  error?: string
  /** Para tablas donde la columna ya dice qué es; la etiqueta sigue para lectores de pantalla. */
  ocultarEtiqueta?: boolean
  className?: string
}) {
  const id = useId()
  return (
    <div className={className}>
      <label htmlFor={id} className={ocultarEtiqueta ? 'sr-only' : 'mb-1.5 block text-sm font-semibold'}>
        {etiqueta}
      </label>
      <div
        className={unir(
          'flex h-12 items-center gap-2 rounded-control border bg-crema px-4 focus-within:border-dorado-borde',
          error ? 'border-peligro' : 'border-dorado-claro',
        )}
      >
        <span aria-hidden className="text-cafe-suave">
          $
        </span>
        <input
          id={id}
          inputMode="numeric"
          autoComplete="off"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          value={valor === null ? '' : miles.format(valor)}
          onChange={(e) => alCambiar(leerPesos(e.target.value))}
          className="min-w-0 flex-1 bg-transparent text-right text-[17px] font-semibold tabular-nums focus:outline-none"
        />
      </div>
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-sm text-peligro-texto">
          {error}
        </p>
      )}
    </div>
  )
}
