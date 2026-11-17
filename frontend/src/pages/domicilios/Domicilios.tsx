import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Buscador } from '../../components/Buscador'
import { Pildoras, Vacio } from '../../components/formulario'
import { Boton, Chip, Tarjeta, TituloTarjeta } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api } from '../../lib/api'
import { hora, pesos } from '../../lib/formato'
import type { Domicilio, EstadoDomicilio } from '../../lib/tipos'
import { telefonoLegible, useDomiciliarios } from '../clientes/datos'
import { DialogoDomiciliario } from './CamposDomicilio'

const ESTADOS: Record<EstadoDomicilio, { texto: string; tono: 'neutro' | 'aviso' | 'exito' | 'peligro' }> = {
  pendiente: { texto: 'Por salir', tono: 'neutro' },
  en_camino: { texto: 'En camino', tono: 'aviso' },
  entregado: { texto: 'Entregado', tono: 'exito' },
  cancelado: { texto: 'Cancelado', tono: 'peligro' },
}
const SIGUIENTE: Partial<Record<EstadoDomicilio, { a: EstadoDomicilio; texto: string }>> = {
  pendiente: { a: 'en_camino', texto: 'Salió' },
  en_camino: { a: 'entregado', texto: 'Entregado' },
}

/** Domicilios del día por estado y domiciliario (RF-13). Se liquidan al cerrar la caja. */
export function Domicilios() {
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const [estado, setEstado] = useState<EstadoDomicilio | ''>('')
  const [domiciliario, setDomiciliario] = useState('')
  const [agregando, setAgregando] = useState(false)
  const domiciliarios = useDomiciliarios()
  const filtros = new URLSearchParams()
  if (estado) filtros.set('estado', estado)
  if (domiciliario) filtros.set('domiciliario_id', domiciliario)
  const domicilios = useQuery({
    queryKey: ['domicilios', estado, domiciliario],
    queryFn: () => api<Domicilio[]>(`/domicilios?${filtros}`),
    refetchInterval: 60_000,
  })
  const cambiar = useMutation({
    mutationFn: ({ id, a }: { id: string; a: EstadoDomicilio }) =>
      api<Domicilio>(`/domicilios/${id}/estado`, { method: 'PATCH', json: { estado: a } }),
    onSuccess: () => void clienteQuery.invalidateQueries({ queryKey: ['domicilios'] }),
    onError: (e) => avisar(e.message, 'error'),
  })
  const lista = domicilios.data ?? []
  const cobrado = lista.filter((d) => d.estado !== 'cancelado').reduce((s, d) => s + d.valor, 0)

  return (
    <Tarjeta className="px-5 py-6 lg:px-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <TituloTarjeta>Domicilios de hoy</TituloTarjeta>
          <p className="mt-1 text-[15px] text-cafe-suave">
            {lista.length} domicilios · {pesos(cobrado)} cobrados · es dinero del domiciliario, no cuenta como venta
          </p>
        </div>
        <Boton variante="secundario" onClick={() => setAgregando(true)}>
          <Plus aria-hidden className="size-5" />
          Domiciliario
        </Boton>
      </div>
      <div className="mt-5 grid gap-3 lg:grid-cols-[1fr_280px] lg:items-center">
        <Pildoras
          etiqueta="Estado del domicilio"
          opciones={[{ valor: '', texto: 'Todos' }, ...Object.entries(ESTADOS).map(([v, e]) => ({ valor: v, texto: e.texto }))]}
          valor={estado}
          alCambiar={(v) => setEstado(v as EstadoDomicilio | '')}
        />
        <Buscador
          etiqueta="Domiciliario"
          ocultarEtiqueta
          opciones={[{ valor: '', texto: 'Todos los domiciliarios' }, ...(domiciliarios.data ?? []).map((d) => ({ valor: d.id, texto: d.nombre }))]}
          valor={domiciliario}
          alCambiar={setDomiciliario}
        />
      </div>
      <div className="mt-4">
        {domicilios.isPending ? (
          <p className="text-cafe-medio">Cargando…</p>
        ) : lista.length === 0 ? (
          <Vacio>No hay domicilios con esos filtros hoy.</Vacio>
        ) : (
          <ul className="grid gap-3">
            {lista.map((d) => {
              const siguiente = SIGUIENTE[d.estado]
              return (
                <li key={d.id} aria-label={`Domicilio de la venta ${d.venta_numero}`} className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-[14px] border border-linea px-5 py-4">
                  <span className="w-[86px] shrink-0 text-[17px] font-semibold text-fucsia-oscuro">{hora(new Date(d.fecha))}</span>
                  <span className="min-w-[220px] flex-1">
                    <span className="block text-[17px] font-semibold [overflow-wrap:anywhere]">{d.direccion}</span>
                    <span className="block text-[15px] text-cafe-medio">
                      {[
                        d.cliente,
                        telefonoLegible(d.telefono),
                        d.encargo_numero ? `Encargo n.º ${String(d.encargo_numero).padStart(4, '0')}` : `Venta n.º ${String(d.venta_numero).padStart(4, '0')}`,
                        d.domiciliario,
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  </span>
                  <span className="text-[16px] font-semibold">{pesos(d.valor)}</span>
                  <Chip tono={ESTADOS[d.estado].tono}>{ESTADOS[d.estado].texto}</Chip>
                  {d.liquidado_en && <Chip tono="exito">Liquidado</Chip>}
                  {siguiente && (
                    <Boton
                      variante="secundario"
                      className="h-10 px-4 text-[15px]"
                      disabled={cambiar.isPending}
                      onClick={() => cambiar.mutate({ id: d.id, a: siguiente.a })}
                    >
                      {siguiente.texto}
                    </Boton>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
      <DialogoDomiciliario abierto={agregando} alCerrar={() => setAgregando(false)} alCrear={() => setAgregando(false)} />
    </Tarjeta>
  )
}
