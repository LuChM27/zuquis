import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Celda, Interruptor, ListaDetalle, PanelDetalle, Tabla } from '../../components/formulario'
import { Boton, Campo, Tarjeta } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api } from '../../lib/api'
import type { CategoriaGasto } from '../../lib/tipos'

/** Categorías de gasto con su cuenta del PUC (las usan los reportes contables). */
export function CategoriasGasto() {
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const categorias = useQuery({
    queryKey: ['categorias-gasto', 'todas'],
    queryFn: () => api<CategoriaGasto[]>('/categorias-gasto?incluir_inactivas=true'),
  })
  const recargar = () => clienteQuery.invalidateQueries({ queryKey: ['categorias-gasto'] })
  const editar = useMutation({
    mutationFn: ({ id, activa }: { id: string; activa: boolean }) =>
      api(`/categorias-gasto/${id}`, { method: 'PATCH', json: { activa } }),
    onSuccess: () => void recargar(),
    onError: (e) => avisar(e.message, 'error'),
  })

  return (
    <ListaDetalle
      lista={
        <Tarjeta>
          <Tabla columnas={[{ texto: 'Categoría' }, { texto: 'Cuenta PUC' }, { texto: 'Activa', derecha: true }]}>
            {categorias.data?.map((c) => (
              <tr key={c.id} className="border-b border-linea last:border-b-0">
                <Celda className="font-medium">{c.nombre}</Celda>
                <Celda className="text-cafe-medio">{c.cuenta_puc ?? '—'}</Celda>
                <Celda derecha>
                  <div className="inline-block">
                    <Interruptor
                      etiqueta={`${c.nombre} activa`}
                      activo={c.activa}
                      alCambiar={(activa) => editar.mutate({ id: c.id, activa })}
                    />
                  </div>
                </Celda>
              </tr>
            ))}
          </Tabla>
        </Tarjeta>
      }
      detalle={<NuevaCategoria alCrear={() => void recargar()} />}
    />
  )
}

function NuevaCategoria({ alCrear }: { alCrear: () => void }) {
  const { avisar } = useAvisos()
  const [nombre, setNombre] = useState('')
  const [puc, setPuc] = useState('')
  const crear = useMutation({
    mutationFn: () => api('/categorias-gasto', { method: 'POST', json: { nombre: nombre.trim(), cuenta_puc: puc || null } }),
    onSuccess: () => {
      avisar('Categoría creada.')
      setNombre('')
      setPuc('')
      alCrear()
    },
    onError: (e) => avisar(e.message, 'error'),
  })
  return (
    <PanelDetalle rotulo="Nueva" titulo="Categoría de gasto">
      <form
        className="grid gap-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (nombre.trim().length >= 2) crear.mutate()
        }}
      >
        <Campo etiqueta="Nombre" value={nombre} maxLength={80} onChange={(e) => setNombre(e.target.value)} />
        <Campo
          etiqueta="Cuenta PUC (opcional)"
          inputMode="numeric"
          placeholder="5135"
          value={puc}
          maxLength={10}
          onChange={(e) => setPuc(e.target.value.replace(/\D/g, ''))}
        />
        <Boton type="submit" disabled={nombre.trim().length < 2 || crear.isPending}>
          Crear categoría
        </Boton>
      </form>
    </PanelDetalle>
  )
}
