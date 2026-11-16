import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSesion } from '../../auth/contexto'
import { FiltroLista } from '../../components/Buscador'
import { Celda, FilaTabla, ListaDetalle, PanelDetalle, Tabla, Vacio } from '../../components/formulario'
import { Boton, Chip, Tarjeta } from '../../components/ui'
import { api } from '../../lib/api'
import { fechaCorta, pesos } from '../../lib/formato'
import type { Cliente, HistorialCliente, Pagina } from '../../lib/tipos'
import { ESTADOS_ENCARGO } from '../encargos/estados'
import { telefonoLegible } from './datos'
import { FormCliente } from './FormCliente'

const TAMANO = 30

/** Espera a que se deje de escribir para no consultar en cada tecla. */
function usePausado<T>(valor: T, ms = 250): T {
  const [v, setV] = useState(valor)
  useEffect(() => {
    const t = setTimeout(() => setV(valor), ms)
    return () => clearTimeout(t)
  }, [valor, ms])
  return v
}

/** Clientes (RF-40): buscar por nombre o teléfono, ver su historial y editar sus datos. */
export function Clientes() {
  const { puede } = useSesion()
  const [busqueda, setBusqueda] = useState('')
  const [pagina, setPagina] = useState(1)
  const [elegido, setElegido] = useState<string | 'nuevo' | null>(null)
  const q = usePausado(busqueda.trim())
  const clientes = useQuery({
    queryKey: ['clientes', 'lista', q, pagina],
    queryFn: () => api<Pagina<Cliente>>(`/clientes?size=${TAMANO}&page=${pagina}${q ? `&q=${encodeURIComponent(q)}` : ''}`),
  })
  const paginas = Math.max(1, Math.ceil((clientes.data?.total ?? 0) / TAMANO))

  return (
    <ListaDetalle
      lista={
        <Tarjeta>
          <div className="flex flex-wrap items-center gap-3">
            <FiltroLista
              className="min-w-0 flex-1"
              etiqueta="Buscar por nombre o teléfono"
              valor={busqueda}
              alCambiar={(v) => {
                setBusqueda(v)
                setPagina(1)
              }}
            />
            {puede('clientes.gestionar') && (
              <Boton onClick={() => setElegido('nuevo')} className="h-11">
                <Plus aria-hidden className="size-5" />
                Nuevo cliente
              </Boton>
            )}
          </div>
          <div className="mt-4">
            {clientes.isPending ? (
              <p className="text-cafe-medio">Cargando…</p>
            ) : clientes.data?.items.length === 0 ? (
              <Vacio>{q ? `Ningún cliente coincide con «${q}».` : 'Aún no hay clientes registrados.'}</Vacio>
            ) : (
              <Tabla columnas={[{ texto: 'Cliente' }, { texto: 'Teléfono' }, { texto: 'Dirección', ocultarMovil: true }]}>
                {clientes.data?.items.map((c) => (
                  <FilaTabla key={c.id} seleccionada={c.id === elegido} alElegir={() => setElegido(c.id)}>
                    <Celda className="font-medium">{c.nombre}</Celda>
                    <Celda className="whitespace-nowrap text-cafe-medio">{telefonoLegible(c.telefono) || '—'}</Celda>
                    <Celda ocultarMovil className="text-cafe-medio">
                      {c.direccion ?? '—'}
                    </Celda>
                  </FilaTabla>
                ))}
              </Tabla>
            )}
          </div>
          {paginas > 1 && (
            <div className="mt-4 flex items-center justify-between gap-3">
              <Boton variante="secundario" disabled={pagina === 1} onClick={() => setPagina(pagina - 1)}>
                Anterior
              </Boton>
              <span className="text-sm text-cafe-suave">
                Página {pagina} de {paginas}
              </span>
              <Boton variante="secundario" disabled={pagina >= paginas} onClick={() => setPagina(pagina + 1)}>
                Siguiente
              </Boton>
            </div>
          )}
        </Tarjeta>
      }
      detalle={
        elegido === 'nuevo' ? (
          <PanelDetalle rotulo="Nuevo" titulo="Cliente">
            <FormCliente alGuardar={(c) => setElegido(c.id)} alCancelar={() => setElegido(null)} />
          </PanelDetalle>
        ) : elegido ? (
          <DetalleCliente key={elegido} id={elegido} />
        ) : (
          <Tarjeta>
            <p className="text-cafe-medio">Elige un cliente para ver sus compras, encargos y domicilios.</p>
          </Tarjeta>
        )
      }
    />
  )
}

function DetalleCliente({ id }: { id: string }) {
  const { puede } = useSesion()
  const [editando, setEditando] = useState(false)
  const historial = useQuery({
    queryKey: ['clientes', 'historial', id],
    queryFn: () => api<HistorialCliente>(`/clientes/${id}/historial`),
  })
  if (historial.isPending) return <Tarjeta>Cargando…</Tarjeta>
  if (historial.isError) return <Tarjeta>{historial.error.message}</Tarjeta>
  const h = historial.data
  const c = h.cliente
  const subtitulo = [telefonoLegible(c.telefono), c.direccion].filter(Boolean).join(' · ')

  return (
    <PanelDetalle rotulo="Cliente" titulo={c.nombre} subtitulo={subtitulo || 'Sin teléfono ni dirección'}>
      {editando ? (
        <FormCliente
          cliente={c}
          alGuardar={() => {
            setEditando(false)
            void historial.refetch()
          }}
          alCancelar={() => setEditando(false)}
        />
      ) : (
        <div className="grid gap-5">
          <div className="flex flex-wrap items-center gap-2">
            <Chip tono={c.autoriza_datos ? 'exito' : 'aviso'}>
              {c.autoriza_datos ? 'Autorizó sus datos' : 'Sin autorización de datos'}
            </Chip>
            {!c.activo && <Chip tono="neutro">Inactivo</Chip>}
          </div>
          {c.notas && <p className="text-cafe-medio">{c.notas}</p>}
          <div className="flex items-baseline justify-between">
            <span className="text-cafe-medio">Total comprado</span>
            <span className="font-serif text-[30px] leading-none">{pesos(h.total_comprado)}</span>
          </div>

          <section>
            <h3 className="text-[13px] font-semibold tracking-[0.08em] text-cafe-suave uppercase">Encargos</h3>
            {h.encargos.length === 0 ? (
              <p className="mt-1.5 text-sm text-cafe-medio">Ninguno.</p>
            ) : (
              <ul className="mt-1.5">
                {h.encargos.map((e) => (
                  <li key={e.id} className="flex items-center justify-between gap-3 border-b border-linea py-2 last:border-b-0">
                    <span className="min-w-0">
                      <span className="block font-medium">
                        N.º {String(e.numero).padStart(4, '0')} · {e.descripcion}
                      </span>
                      <span className="text-sm text-cafe-suave">
                        {fechaCorta(new Date(e.fecha_entrega))} · {pesos(e.total)}
                      </span>
                    </span>
                    <Chip tono={ESTADOS_ENCARGO[e.estado].tono}>{ESTADOS_ENCARGO[e.estado].texto}</Chip>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h3 className="text-[13px] font-semibold tracking-[0.08em] text-cafe-suave uppercase">Compras</h3>
            {h.ventas.length === 0 ? (
              <p className="mt-1.5 text-sm text-cafe-medio">Ninguna a su nombre.</p>
            ) : (
              <ul className="mt-1.5">
                {h.ventas.map((v) => (
                  <li key={v.id} className="flex justify-between gap-3 border-b border-linea py-2 text-[15px] last:border-b-0">
                    <span>
                      Venta n.º {String(v.numero).padStart(4, '0')}{' '}
                      <span className="text-cafe-suave">· {fechaCorta(new Date(v.fecha))}</span>
                    </span>
                    <span className={v.estado === 'anulada' ? 'text-cafe-suave line-through' : 'font-semibold'}>{pesos(v.total)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h3 className="text-[13px] font-semibold tracking-[0.08em] text-cafe-suave uppercase">Domicilios</h3>
            {h.domicilios.length === 0 ? (
              <p className="mt-1.5 text-sm text-cafe-medio">Ninguno.</p>
            ) : (
              <ul className="mt-1.5">
                {h.domicilios.map((d) => (
                  <li key={d.id} className="flex justify-between gap-3 border-b border-linea py-2 text-[15px] last:border-b-0">
                    <span>
                      {d.direccion} <span className="text-cafe-suave">· {fechaCorta(new Date(d.fecha))}</span>
                    </span>
                    <span>{pesos(d.valor)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {puede('clientes.gestionar') && (
            <Boton variante="secundario" onClick={() => setEditando(true)}>
              Editar datos
            </Boton>
          )}
        </div>
      )}
    </PanelDetalle>
  )
}
