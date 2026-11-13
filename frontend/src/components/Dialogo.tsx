import { X } from 'lucide-react'
import { useEffect, useId, useRef, type ReactNode } from 'react'
import { unir } from '../lib/clases'

/** normal: formulario corto · ancho: tablas (kardex) · hoja: hoja inferior en celular. */
export type FormaDialogo = 'normal' | 'ancho' | 'hoja'

const FORMAS: Record<FormaDialogo, string> = {
  normal: 'm-auto w-[min(440px,calc(100%-2rem))] rounded-tarjeta',
  ancho: 'm-auto w-[min(920px,calc(100%-2rem))] rounded-tarjeta',
  hoja: 'mx-0 mt-auto mb-0 max-h-[88dvh] w-full max-w-none rounded-t-tarjeta border-b-0',
}

/**
 * Diálogo modal sobre <dialog> nativo: atrapa el foco, cierra con Esc y devuelve el foco al
 * botón que lo abrió. Para confirmaciones y formularios cortos que no merecen página.
 */
export function Dialogo({
  abierto,
  alCerrar,
  titulo,
  rotulo,
  forma = 'normal',
  children,
}: {
  abierto: boolean
  alCerrar: () => void
  titulo: string
  /** Línea pequeña sobre el título ("DETALLE", "KARDEX"). */
  rotulo?: string
  forma?: FormaDialogo
  children: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const idTitulo = useId()

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (abierto && !d.open) {
      const previo = document.activeElement as HTMLElement | null
      d.showModal?.()
      return () => previo?.focus()
    }
    if (!abierto && d.open) d.close()
  }, [abierto])

  return (
    <dialog
      ref={ref}
      aria-labelledby={idTitulo}
      onCancel={(e) => {
        e.preventDefault()
        alCerrar()
      }}
      onClick={(e) => e.target === ref.current && alCerrar()}
      className={unir(
        'border border-dorado-borde bg-blanco p-0 text-cafe backdrop:bg-cafe/35',
        FORMAS[forma],
      )}
    >
      {abierto && (
        <div className="p-6">
          {forma === 'hoja' && <div aria-hidden className="mx-auto -mt-2 mb-3 h-1.5 w-12 rounded-full bg-pista" />}
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              {rotulo && (
                <p className="text-[13px] font-semibold tracking-[0.12em] text-dorado-texto uppercase">{rotulo}</p>
              )}
              <h2 id={idTitulo} className="font-serif text-[28px] leading-tight font-medium break-words">
                {titulo}
              </h2>
            </div>
            <button
              type="button"
              onClick={alCerrar}
              aria-label="Cerrar"
              className="-mt-1 -mr-2 grid size-10 shrink-0 place-items-center rounded-control hover:bg-crema"
            >
              <X aria-hidden className="size-5" />
            </button>
          </div>
          <div className="mt-4">{children}</div>
        </div>
      )}
    </dialog>
  )
}
