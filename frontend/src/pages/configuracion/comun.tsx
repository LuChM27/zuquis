import { Plus } from 'lucide-react'
import type { ReactNode } from 'react'
import { Tarjeta } from '../../components/ui'

/** Tarjeta de lista con título y botón "Nuevo ..." arriba. */
export function TarjetaLista({
  titulo,
  nuevo,
  alNuevo,
  children,
}: {
  titulo: string
  nuevo?: string
  alNuevo?: () => void
  children: ReactNode
}) {
  return (
    <Tarjeta className="min-w-0">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="font-serif text-[28px] leading-tight font-medium">{titulo}</h2>
        {nuevo && alNuevo && (
          <button
            type="button"
            onClick={alNuevo}
            className="inline-flex h-10 items-center gap-1.5 rounded-control px-3 font-semibold text-fucsia hover:bg-rosa-suave"
          >
            <Plus aria-hidden className="size-[18px]" strokeWidth={2.2} />
            {nuevo}
          </button>
        )}
      </div>
      {children}
    </Tarjeta>
  )
}

/** Pie del formulario del panel: botón principal a lo ancho y acciones secundarias debajo. */
export function PieFormulario({ children }: { children: ReactNode }) {
  return <div className="mt-6 flex flex-col gap-2.5">{children}</div>
}
