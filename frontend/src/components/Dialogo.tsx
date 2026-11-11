import { X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'

/**
 * Diálogo modal sobre <dialog> nativo: atrapa el foco, cierra con Esc y devuelve el foco al
 * botón que lo abrió. Para confirmaciones y formularios cortos que no merecen página.
 */
export function Dialogo({
  abierto,
  alCerrar,
  titulo,
  children,
}: {
  abierto: boolean
  alCerrar: () => void
  titulo: string
  children: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)

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
      aria-labelledby="dialogo-titulo"
      onCancel={(e) => {
        e.preventDefault()
        alCerrar()
      }}
      onClick={(e) => e.target === ref.current && alCerrar()}
      className="m-auto w-[min(440px,calc(100%-2rem))] rounded-tarjeta border border-dorado-borde bg-blanco p-0 text-cafe backdrop:bg-cafe/35"
    >
      {abierto && (
        <div className="p-6">
          <div className="flex items-start justify-between gap-4">
            <h2 id="dialogo-titulo" className="font-serif text-[28px] leading-tight font-medium">
              {titulo}
            </h2>
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
