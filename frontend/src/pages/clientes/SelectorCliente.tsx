import { UserPlus } from 'lucide-react'
import { useState } from 'react'
import { useSesion } from '../../auth/contexto'
import { Buscador } from '../../components/Buscador'
import type { Cliente } from '../../lib/tipos'
import { telefonoLegible, useClientes } from './datos'
import { DialogoCliente } from './FormCliente'

/**
 * Elegir un cliente escribiendo su nombre o teléfono, o crearlo ahí mismo. `alCambiar` recibe
 * el cliente completo para llenar dirección y teléfono de una vez.
 */
export function SelectorCliente({
  valor,
  alCambiar,
  etiqueta = 'Cliente',
  opcional,
  error,
}: {
  valor: string
  alCambiar: (c: Cliente | null) => void
  etiqueta?: string
  /** Agrega "Sin cliente" como primera opción. */
  opcional?: boolean
  error?: string
}) {
  const { puede } = useSesion()
  const clientes = useClientes()
  const [creando, setCreando] = useState(false)
  const lista = clientes.data ?? []
  const opciones = [
    ...(opcional ? [{ valor: '', texto: 'Sin cliente' }] : []),
    ...lista.map((c) => ({
      valor: c.id,
      texto: c.nombre,
      detalle: telefonoLegible(c.telefono),
      busqueda: c.telefono ?? undefined,
    })),
  ]
  return (
    <div>
      <div className="flex items-end gap-2">
        <Buscador
          className="min-w-0 flex-1"
          etiqueta={etiqueta}
          placeholder={clientes.isPending ? 'Cargando clientes…' : 'Nombre o teléfono'}
          opciones={opciones}
          valor={valor}
          alCambiar={(id) => alCambiar(lista.find((c) => c.id === id) ?? null)}
          error={error}
        />
        {puede('clientes.gestionar') && (
          <button
            type="button"
            onClick={() => setCreando(true)}
            aria-label="Crear cliente nuevo"
            title="Crear cliente nuevo"
            className="grid size-12 shrink-0 place-items-center rounded-control border border-dorado-claro bg-blanco hover:border-dorado-borde"
          >
            <UserPlus aria-hidden className="size-5" strokeWidth={1.7} />
          </button>
        )}
      </div>
      <DialogoCliente
        abierto={creando}
        alCerrar={() => setCreando(false)}
        alElegir={(c) => {
          setCreando(false)
          alCambiar(c)
        }}
      />
    </div>
  )
}
