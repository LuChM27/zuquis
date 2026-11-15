import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { CampoDinero } from '../../components/CampoDinero'
import { Boton } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api } from '../../lib/api'

/** Abrir caja con el efectivo con el que arranca el turno (RF-17). */
export function FormAbrirCaja({ textoBoton = 'Abrir caja', alAbrir }: { textoBoton?: string; alAbrir?: () => void }) {
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const [base, setBase] = useState<number | null>(null)
  const abrir = useMutation({
    mutationFn: () => api('/caja/abrir', { method: 'POST', json: { base_inicial: base ?? 0 } }),
    onSuccess: () => {
      avisar('Caja abierta.')
      void clienteQuery.invalidateQueries({ queryKey: ['caja'] })
      alAbrir?.()
    },
    onError: (e) => {
      avisar(e.message, 'error')
      void clienteQuery.invalidateQueries({ queryKey: ['caja'] })
    },
  })
  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        abrir.mutate()
      }}
    >
      <CampoDinero etiqueta="Base inicial en efectivo" valor={base} alCambiar={setBase} />
      <Boton type="submit" disabled={base === null || abrir.isPending}>
        {abrir.isPending ? 'Abriendo…' : textoBoton}
      </Boton>
    </form>
  )
}
