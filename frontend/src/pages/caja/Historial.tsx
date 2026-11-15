import { useQuery } from '@tanstack/react-query'
import { Printer } from 'lucide-react'
import { useState } from 'react'
import { Celda, FilaTabla, ListaDetalle, PanelDetalle, Tabla, Vacio } from '../../components/formulario'
import { Boton, Chip, Tarjeta } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api } from '../../lib/api'
import { unir } from '../../lib/clases'
import { fechaCorta, hora, pesos } from '../../lib/formato'
import { abrirPdf } from '../../lib/pdf'
import type { Pagina, SesionDetalle, SesionResumen } from '../../lib/tipos'
import { DeDondeSaleElEfectivo, ResumenDelTurno } from './Resumenes'

const TAMANO = 20

function Diferencia({ valor }: { valor: number | null }) {
  if (valor === null) return <span className="text-cafe-suave">—</span>
  return (
    <span className={unir('font-semibold', valor === 0 ? 'text-exito-texto' : 'text-peligro-texto')}>
      {pesos(valor, { signo: true })}
    </span>
  )
}

/** Historial de cierres con su detalle y reimpresión del resumen (RF-20). */
export function Historial({ elegida, alElegir }: { elegida?: string; alElegir: (id: string) => void }) {
  const [pagina, setPagina] = useState(1)
  const sesiones = useQuery({
    queryKey: ['caja', 'sesiones', pagina],
    queryFn: () => api<Pagina<SesionResumen>>(`/caja/sesiones?page=${pagina}&size=${TAMANO}`),
  })
  const paginas = Math.max(1, Math.ceil((sesiones.data?.total ?? 0) / TAMANO))
  return (
    <ListaDetalle
      lista={
        <Tarjeta>
          {sesiones.isPending ? (
            <p className="text-cafe-medio">Cargando…</p>
          ) : sesiones.data?.items.length === 0 ? (
            <Vacio>Todavía no hay cierres de caja.</Vacio>
          ) : (
            <Tabla
              columnas={[
                { texto: 'Abierta' },
                { texto: 'Responsable', ocultarMovil: true },
                { texto: 'Efectivo esperado', derecha: true, ocultarMovil: true },
                { texto: 'Diferencia', derecha: true },
              ]}
            >
              {sesiones.data?.items.map((s) => (
                <FilaTabla key={s.id} seleccionada={s.id === elegida} alElegir={() => alElegir(s.id)}>
                  <Celda>
                    <span className="block font-medium">{fechaCorta(new Date(s.abierta_en))}</span>
                    <span className="block text-sm text-cafe-suave">
                      {hora(new Date(s.abierta_en))}
                      {s.cerrada_en ? ` a ${hora(new Date(s.cerrada_en))}` : ''}
                    </span>
                  </Celda>
                  <Celda ocultarMovil>{s.responsable}</Celda>
                  <Celda derecha ocultarMovil>
                    {pesos(s.efectivo_esperado)}
                  </Celda>
                  <Celda derecha>{s.estado === 'abierta' ? <Chip tono="exito">Abierta</Chip> : <Diferencia valor={s.diferencia_total} />}</Celda>
                </FilaTabla>
              ))}
            </Tabla>
          )}
          {paginas > 1 && (
            <nav aria-label="Páginas" className="mt-4 flex items-center justify-between gap-3">
              <Boton variante="secundario" disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}>
                Anterior
              </Boton>
              <p className="text-sm text-cafe-medio">
                Página {pagina} de {paginas}
              </p>
              <Boton variante="secundario" disabled={pagina >= paginas} onClick={() => setPagina((p) => p + 1)}>
                Siguiente
              </Boton>
            </nav>
          )}
        </Tarjeta>
      }
      detalle={elegida ? <DetalleSesion id={elegida} /> : null}
    />
  )
}

function DetalleSesion({ id }: { id: string }) {
  const { avisar } = useAvisos()
  const detalle = useQuery({ queryKey: ['caja', 'sesion', id], queryFn: () => api<SesionDetalle>(`/caja/sesiones/${id}`) })
  if (!detalle.data) return <Tarjeta><p className="text-cafe-medio">Cargando…</p></Tarjeta>
  const s = detalle.data
  const abierta = new Date(s.abierta_en)
  return (
    <PanelDetalle
      rotulo={s.estado === 'abierta' ? 'Caja abierta' : 'Cierre'}
      titulo={fechaCorta(abierta)}
      subtitulo={`${hora(abierta)}${s.cerrada_en ? ` a ${hora(new Date(s.cerrada_en))}` : ''}${s.responsable ? ` · ${s.responsable}` : ''}`}
    >
      <h3 className="text-[13px] font-semibold tracking-[0.08em] text-cafe-suave uppercase">Arqueo</h3>
      <dl className="mt-2">
        {s.arqueos.map((a) => (
          <div key={a.metodo_pago_id} className="flex items-baseline justify-between gap-3 border-b border-linea py-2">
            <dt>
              <span className="block font-medium">{a.metodo}</span>
              <span className="block text-sm text-cafe-suave">
                Esperado {pesos(a.esperado)}
                {a.contado !== null && ` · contado ${pesos(a.contado)}`}
              </span>
            </dt>
            <dd>
              <Diferencia valor={a.diferencia} />
            </dd>
          </div>
        ))}
      </dl>
      {s.observacion && (
        <p className="mt-3 rounded-control bg-crema p-3 text-[15px]">
          <span className="font-semibold">Observación:</span> {s.observacion}
        </p>
      )}
      <h3 className="mt-5 text-[13px] font-semibold tracking-[0.08em] text-cafe-suave uppercase">De dónde sale el efectivo</h3>
      <div className="mt-1 text-[15px]">
        <DeDondeSaleElEfectivo lineas={s.efectivo} total={s.efectivo_esperado} />
      </div>
      <h3 className="mt-5 text-[13px] font-semibold tracking-[0.08em] text-cafe-suave uppercase">Resumen del turno</h3>
      <div className="mt-1 text-[15px]">
        <ResumenDelTurno resumen={s.resumen} />
      </div>
      {s.estado === 'cerrada' && (
        <Boton
          variante="secundario"
          className="mt-5 w-full"
          onClick={() => void abrirPdf(`/caja/sesiones/${s.id}/resumen`).catch((e: Error) => avisar(e.message, 'error'))}
        >
          <Printer aria-hidden className="size-5" strokeWidth={1.7} />
          Reimprimir resumen
        </Boton>
      )}
    </PanelDetalle>
  )
}
