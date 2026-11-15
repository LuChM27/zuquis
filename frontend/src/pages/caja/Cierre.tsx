import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Printer } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { CampoDinero } from '../../components/CampoDinero'
import { Dialogo } from '../../components/Dialogo'
import { AreaTexto, Aviso } from '../../components/formulario'
import { Boton, Chip, EncabezadoPagina, Tarjeta, TituloTarjeta } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api, ErrorApi } from '../../lib/api'
import { unir } from '../../lib/clases'
import { fechaConDia, hora, pesos } from '../../lib/formato'
import { abrirPdf } from '../../lib/pdf'
import type { SesionDetalle, VistaCierre } from '../../lib/tipos'
import { DeDondeSaleElEfectivo, ResumenDelTurno } from './Resumenes'

type EstadoPaso = 'hecho' | 'actual' | 'pendiente'

function Paso({ numero, texto, estado }: { numero: number; texto: string; estado: EstadoPaso }) {
  return (
    <li
      aria-current={estado === 'actual' ? 'step' : undefined}
      className={unir(
        'flex h-[46px] shrink-0 items-center gap-2.5 rounded-full border pr-5 pl-2 text-[15px] font-semibold whitespace-nowrap',
        estado === 'hecho' && 'border-transparent bg-exito-fondo text-exito-texto',
        estado === 'actual' && 'border-transparent bg-rosa-suave text-fucsia-oscuro',
        estado === 'pendiente' && 'border-dorado-claro bg-blanco font-medium text-cafe',
      )}
    >
      <span
        aria-hidden
        className={unir(
          'grid size-[30px] place-items-center rounded-full text-sm font-bold',
          estado === 'hecho' && 'bg-exito text-white',
          estado === 'actual' && 'bg-fucsia text-white',
          estado === 'pendiente' && 'bg-pista text-cafe',
        )}
      >
        {numero}
      </span>
      {texto}
      <span className="sr-only">{estado === 'hecho' ? ' (listo)' : estado === 'actual' ? ' (paso actual)' : ''}</span>
    </li>
  )
}

/** Cierre de caja en 3 pasos, como el mockup "Cierre de caja" (RF-19, RN-13, RN-14, RN-18). */
export function Cierre({ navegacion, alCerrada }: { navegacion: ReactNode; alCerrada: (sesionId: string) => void }) {
  const vista = useQuery({ queryKey: ['caja', 'cierre'], queryFn: () => api<VistaCierre>('/caja/actual/cierre') })
  if (vista.isPending || vista.isError) {
    return (
      <>
        <EncabezadoPagina titulo="Cierre de caja" />
        {navegacion}
        {vista.isPending ? (
          <p className="text-cafe-medio">Cargando…</p>
        ) : (
          <Aviso>
            {vista.error instanceof ErrorApi && vista.error.codigo === 'CAJA_CERRADA' ? 'No hay caja abierta para cerrar.' : vista.error.message}
          </Aviso>
        )}
      </>
    )
  }
  return <FormCierre vista={vista.data} navegacion={navegacion} alCerrada={alCerrada} />
}

function FormCierre({
  vista,
  navegacion,
  alCerrada,
}: {
  vista: VistaCierre
  navegacion: ReactNode
  alCerrada: (sesionId: string) => void
}) {
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const [contado, setContado] = useState<Record<string, number | null>>({})
  const [observacion, setObservacion] = useState('')
  const [intento, setIntento] = useState(false)
  const [cerrada, setCerrada] = useState<SesionDetalle | null>(null)

  const filas = vista.arqueo.map((a) => {
    const c = contado[a.metodo_pago_id] ?? null
    return { ...a, contado: c, diferencia: c === null ? null : c - a.esperado }
  })
  const faltan = filas.filter((f) => f.esperado !== 0 && f.contado === null)
  const hayDiferencia = filas.some((f) => f.diferencia !== null && f.diferencia !== 0)
  const sinObservacion = hayDiferencia && observacion.trim() === ''
  const pendientes = vista.domicilios_sin_liquidar
  const listo = pendientes === 0 && faltan.length === 0 && !sinObservacion

  const cerrar = useMutation({
    mutationFn: () =>
      api<SesionDetalle>('/caja/cerrar', {
        method: 'POST',
        json: {
          contado: filas.map((f) => ({ metodo_pago_id: f.metodo_pago_id, contado: f.contado ?? 0 })),
          observacion: observacion.trim() || null,
        },
      }),
    // La caja se recarga al salir del aviso: si no, esta pantalla desaparece con el aviso.
    onSuccess: setCerrada,
    onError: (e) => avisar(e.message, 'error'),
  })

  const sesion = vista.sesion
  const abierta = new Date(sesion.abierta_en)
  return (
    <div>
      <EncabezadoPagina
        contexto={`Caja del ${fechaConDia(abierta).toLowerCase()} · abierta ${hora(abierta)} · base ${pesos(sesion.base_inicial)}`}
        titulo="Cierre de caja"
      />
      {navegacion}
      <ol aria-label="Pasos del cierre" className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-1 lg:mx-0 lg:px-0">
        <Paso numero={1} texto="Liquidar domicilios" estado={pendientes === 0 ? 'hecho' : 'actual'} />
        <Paso
          numero={2}
          texto="Contar el dinero"
          estado={pendientes > 0 ? 'pendiente' : faltan.length === 0 && !sinObservacion ? 'hecho' : 'actual'}
        />
        <Paso numero={3} texto="Confirmar y cerrar" estado={listo ? 'actual' : 'pendiente'} />
      </ol>

      <Tarjeta className="mt-5 flex flex-wrap items-center justify-between gap-4 px-6 py-5">
        <div className="min-w-0">
          <TituloTarjeta>Domicilios del turno</TituloTarjeta>
          <p className="mt-1 text-[15px] text-cafe-suave">
            {pendientes > 0
              ? `${pendientes} domicilios sin liquidar: entrégale al domiciliario lo suyo antes de cerrar.`
              : 'Lo cobrado por domicilios es dinero del domiciliario, no cuenta como venta.'}
          </p>
        </div>
        {pendientes > 0 ? (
          <Chip tono="peligro">{pendientes} sin liquidar</Chip>
        ) : (
          <span className="rounded-control bg-exito-fondo px-6 py-3.5 text-[16px] font-semibold text-exito-texto">
            {vista.resumen.domicilios_entregados > 0
              ? `Entregados ${pesos(vista.resumen.domicilios_entregados)} al domiciliario`
              : 'Nada por liquidar'}
          </span>
        )}
      </Tarjeta>

      <Tarjeta className="mt-5 px-6 py-6">
        <TituloTarjeta>Arqueo por método de pago</TituloTarjeta>
        <p className="mt-2 text-[15px] text-cafe-medio">
          El sistema calcula cuánto debería haber. Tú escribes lo que contaste o lo que ves en la app del banco.
        </p>
        <div className="-mx-6 mt-5 overflow-x-auto px-6">
          <table className="w-full min-w-[560px] border-collapse text-left">
            <thead>
              <tr className="border-b border-dorado-claro">
                {['Método', 'Debería haber', 'Contado', 'Diferencia'].map((t, i) => (
                  <th
                    key={t}
                    scope="col"
                    className={unir(
                      'px-3 pb-3 text-[13px] font-semibold tracking-[0.08em] text-cafe-suave uppercase',
                      i > 0 && 'text-right',
                    )}
                  >
                    {t}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filas.map((f) => (
                <tr key={f.metodo_pago_id} className="border-b border-linea">
                  <th scope="row" className="h-[66px] px-3 text-left text-[17px] font-semibold">
                    {f.metodo}
                  </th>
                  <td className="px-3 text-right text-[17px] text-cafe-medio">{pesos(f.esperado)}</td>
                  <td className="px-3">
                    <CampoDinero
                      etiqueta={`Contado en ${f.metodo}`}
                      ocultarEtiqueta
                      className="ml-auto w-[150px] lg:w-[200px]"
                      valor={f.contado}
                      alCambiar={(v) => setContado((c) => ({ ...c, [f.metodo_pago_id]: v }))}
                      error={intento && f.esperado !== 0 && f.contado === null ? ' ' : undefined}
                    />
                  </td>
                  <td
                    className={unir(
                      'px-3 text-right text-[17px] font-bold',
                      f.diferencia === null ? 'text-cafe-suave' : f.diferencia === 0 ? 'text-exito-texto' : 'text-peligro-texto',
                    )}
                  >
                    {f.diferencia === null ? '—' : pesos(f.diferencia, { signo: true })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <AreaTexto
          className="mt-5"
          etiqueta="Observación (obligatoria si hay diferencia)"
          rows={2}
          maxLength={500}
          value={observacion}
          onChange={(e) => setObservacion(e.target.value)}
          aria-invalid={intento && sinObservacion ? true : undefined}
        />
        {intento && faltan.length > 0 && (
          <p role="alert" className="mt-2 text-sm text-peligro-texto">
            Falta escribir lo contado en: {faltan.map((f) => f.metodo).join(', ')}.
          </p>
        )}
        {intento && sinObservacion && (
          <p role="alert" className="mt-2 text-sm text-peligro-texto">
            Hay diferencias entre lo contado y lo esperado: escribe una observación.
          </p>
        )}
      </Tarjeta>

      <div className="mt-5 grid items-stretch gap-5 lg:grid-cols-2">
        <Tarjeta className="px-6 py-6">
          <TituloTarjeta>De dónde sale el efectivo</TituloTarjeta>
          <div className="mt-3">
            <DeDondeSaleElEfectivo lineas={vista.efectivo} total={vista.efectivo_esperado} />
          </div>
        </Tarjeta>
        <Tarjeta className="flex flex-col px-6 py-6">
          <TituloTarjeta>Resumen del turno</TituloTarjeta>
          <div className="mt-3">
            <ResumenDelTurno resumen={vista.resumen} />
          </div>
          <button
            type="button"
            disabled={cerrar.isPending}
            onClick={() => {
              setIntento(true)
              if (listo) cerrar.mutate()
            }}
            className="mt-auto h-[56px] w-full rounded-[16px] bg-fucsia text-[18px] font-bold text-white transition-colors hover:bg-fucsia-oscuro disabled:opacity-60 lg:mt-8"
          >
            {cerrar.isPending ? 'Cerrando…' : 'Confirmar y cerrar caja'}
          </button>
        </Tarjeta>
      </div>

      <CajaCerrada
        detalle={cerrada}
        alSeguir={() => {
          if (!cerrada) return
          void clienteQuery.invalidateQueries({ queryKey: ['caja'] })
          alCerrada(cerrada.id)
        }}
      />
    </div>
  )
}

function CajaCerrada({ detalle, alSeguir }: { detalle: SesionDetalle | null; alSeguir: () => void }) {
  const { avisar } = useAvisos()
  const diferencia = detalle?.diferencia_total ?? 0
  return (
    <Dialogo abierto={detalle !== null} alCerrar={alSeguir} titulo="Caja cerrada" rotulo="Cierre registrado">
      {detalle && (
        <div className="grid gap-4">
          <p className="text-cafe-medio">
            {diferencia === 0
              ? 'Lo contado coincide con lo esperado.'
              : `Diferencia total de ${pesos(diferencia, { signo: true })}; quedó registrada con la observación.`}
          </p>
          <div className="grid grid-cols-2 gap-3">
            <Boton
              variante="secundario"
              onClick={() =>
                void abrirPdf(`/caja/sesiones/${detalle.id}/resumen`).catch((e: Error) => avisar(e.message, 'error'))
              }
            >
              <Printer aria-hidden className="size-5" strokeWidth={1.7} />
              Imprimir
            </Boton>
            <Boton onClick={alSeguir} autoFocus>
              Ver historial
            </Boton>
          </div>
        </div>
      )}
    </Dialogo>
  )
}
