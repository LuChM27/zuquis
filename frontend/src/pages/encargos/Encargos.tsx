import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { useSesion } from '../../auth/contexto'
import { Aviso, Pildoras } from '../../components/formulario'
import { Boton, Chip, EncabezadoPagina, Tarjeta } from '../../components/ui'
import { api } from '../../lib/api'
import { unir } from '../../lib/clases'
import { hora, pesos } from '../../lib/formato'
import type { ConteoDia, Encargo, Pagina } from '../../lib/tipos'
import { hoyIso } from '../../lib/unidades'
import { Clientes } from '../clientes/Clientes'
import { Domicilios } from '../domicilios/Domicilios'
import { DetalleEncargo } from './DetalleEncargo'
import { ESTADOS_ENCARGO } from './estados'
import { DialogoEncargo } from './FormEncargo'
import {
  DIAS_CORTOS,
  diaDeSemana,
  diaLocal,
  diasDelMes,
  etiquetaSemana,
  lunesDe,
  numeroDia,
  primeroDelMes,
  sumarDias,
  sumarMeses,
  tituloDia,
  tituloMes,
} from './fechas'

type Seccion = 'semana' | 'mes' | 'domicilios' | 'clientes'

const contar = (n: number) => (n === 0 ? 'Sin encargos' : n === 1 ? '1 encargo' : `${n} encargos`)

/** Encargos y abonos (mockup "Encargos y abonos", RF-34 a RF-39), domicilios del día y clientes. */
export function Encargos() {
  const { puede } = useSesion()
  const [params, setParams] = useSearchParams()
  const hoy = hoyIso()
  const dia = params.get('dia') ?? hoy
  const lunes = lunesDe(dia)
  const elegido = params.get('encargo')
  const seccion = (params.get('seccion') as Seccion) || 'semana'
  const [formulario, setFormulario] = useState<'nuevo' | Encargo | null>(null)

  const fijar = (cambios: Record<string, string | null>) => {
    const p = new URLSearchParams(params)
    for (const [k, v] of Object.entries(cambios)) {
      if (v === null) p.delete(k)
      else p.set(k, v)
    }
    setParams(p)
  }

  const semana = useQuery({
    queryKey: ['encargos', 'semana', lunes],
    queryFn: () => api<Pagina<Encargo>>(`/encargos?desde=${lunes}&hasta=${sumarDias(lunes, 6)}&size=200`),
    enabled: seccion === 'semana',
  })
  const deHoy = useQuery({
    queryKey: ['encargos', 'hoy', hoy],
    queryFn: () => api<Pagina<Encargo>>(`/encargos?desde=${hoy}&hasta=${hoy}&size=200`),
  })
  const pendientesHoy = (deHoy.data?.items ?? []).filter((e) => ['pendiente', 'en_produccion', 'listo'].includes(e.estado))

  const activos = (semana.data?.items ?? []).filter((e) => e.estado !== 'cancelado')
  const delDia = (semana.data?.items ?? []).filter((e) => diaLocal(e.fecha_entrega) === dia)
  const encargo = (semana.data?.items ?? []).find((e) => e.id === elegido) ?? delDia.find((e) => e.estado !== 'cancelado' && e.estado !== 'entregado') ?? delDia[0]

  const contexto =
    seccion === 'semana' ? `${etiquetaSemana(lunes)} · ${contar(activos.length).toLowerCase()}` : seccion === 'mes' ? 'Encargos por fecha de entrega' : seccion === 'domicilios' ? 'Lo que sale a domicilio hoy' : 'Quién encarga y qué ha comprado'

  return (
    <>
      <EncabezadoPagina
        contexto={contexto}
        titulo="Encargos"
        acciones={
          puede('encargos.crear') && (
            <Boton onClick={() => setFormulario('nuevo')} className="h-[58px] px-[34px] text-[19px]">
              Nuevo encargo
            </Boton>
          )
        }
      />
      <div className="mb-5">
        <Pildoras
          etiqueta="Secciones de encargos"
          opciones={[
            { valor: 'semana', texto: 'Semana' },
            { valor: 'mes', texto: 'Mes' },
            { valor: 'domicilios', texto: 'Domicilios de hoy' },
            { valor: 'clientes', texto: 'Clientes' },
          ]}
          valor={seccion}
          alCambiar={(v) => fijar({ seccion: v === 'semana' ? null : v, encargo: null })}
        />
      </div>

      {seccion !== 'semana' || dia !== hoy
        ? pendientesHoy.length > 0 && (
            <div className="mb-4">
              <Aviso tono="aviso">
                Hoy hay {contar(pendientesHoy.length).toLowerCase()} por entregar.{' '}
                <button type="button" className="font-semibold text-fucsia underline" onClick={() => fijar({ seccion: null, dia: null, encargo: null })}>
                  Ver los de hoy
                </button>
              </Aviso>
            </div>
          )
        : null}

      {seccion === 'semana' && (
        <>
          <div className="mb-[22px] flex items-stretch gap-2">
            <button type="button" aria-label="Semana anterior" onClick={() => fijar({ dia: sumarDias(lunes, -7), encargo: null })} className="grid w-10 shrink-0 place-items-center rounded-control hover:bg-blanco">
              <ChevronLeft aria-hidden className="size-6" />
            </button>
            <div role="tablist" aria-label="Días de la semana" className="-mx-1 flex min-w-0 flex-1 gap-3 overflow-x-auto px-1 pb-1 lg:grid lg:grid-cols-7 lg:gap-[18px]">
              {Array.from({ length: 7 }, (_, i) => {
                const d = sumarDias(lunes, i)
                const n = activos.filter((e) => diaLocal(e.fecha_entrega) === d).length
                const actual = d === dia
                return (
                  <button
                    key={d}
                    type="button"
                    role="tab"
                    aria-selected={actual}
                    onClick={() => fijar({ dia: d, encargo: null })}
                    className={unir(
                      'flex h-[118px] min-w-[96px] flex-col items-center justify-center rounded-tarjeta border bg-blanco transition-colors',
                      actual ? 'border-2 border-fucsia bg-rosa-suave' : 'border-dorado-claro hover:border-dorado-borde',
                    )}
                  >
                    <span className={unir('text-[15px]', actual ? 'font-semibold text-fucsia-oscuro' : 'text-cafe-medio')}>
                      {DIAS_CORTOS[i]}
                      {d === hoy && ' · hoy'}
                    </span>
                    <span className="font-serif text-[36px] leading-tight font-medium">{numeroDia(d)}</span>
                    <span className={unir('text-[14px]', actual ? 'font-semibold' : 'text-cafe-medio')}>{contar(n)}</span>
                  </button>
                )
              })}
            </div>
            <button type="button" aria-label="Semana siguiente" onClick={() => fijar({ dia: sumarDias(lunes, 7), encargo: null })} className="grid w-10 shrink-0 place-items-center rounded-control hover:bg-blanco">
              <ChevronRight aria-hidden className="size-6" />
            </button>
          </div>

          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_420px]">
            <Tarjeta className="px-5 py-6 lg:px-[28px] lg:py-[30px]">
              <h2 className="font-serif text-[32px] leading-tight font-medium">{tituloDia(dia, hoy)}</h2>
              {semana.isPending ? (
                <p className="mt-4 text-cafe-medio">Cargando…</p>
              ) : delDia.length === 0 ? (
                <p className="py-10 text-center text-cafe-medio">No hay encargos para este día.</p>
              ) : (
                <ul className="mt-5 grid gap-3">
                  {delDia.map((e) => {
                    const actual = e.id === encargo?.id
                    return (
                      <li key={e.id}>
                        <button
                          type="button"
                          aria-current={actual || undefined}
                          onClick={() => fijar({ encargo: e.id })}
                          className={unir(
                            // Celular: hora y estado arriba, luego descripción y saldo. Escritorio: una fila, como el mockup.
                            'grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 rounded-[14px] border px-5 py-4 text-left transition-colors lg:grid-cols-[100px_minmax(0,1fr)_auto_auto] lg:gap-x-5',
                            actual ? 'border-dorado-borde bg-crema' : 'border-linea hover:border-dorado-claro',
                          )}
                        >
                          <span className="order-1 text-[18px] font-semibold text-fucsia-oscuro">{hora(new Date(e.fecha_entrega))}</span>
                          <span className="order-3 col-span-2 min-w-0 lg:order-2 lg:col-span-1">
                            <span className={unir('block text-[18px] font-semibold [overflow-wrap:anywhere]', e.estado === 'cancelado' && 'line-through')}>{e.descripcion}</span>
                            <span className="block text-[15px] text-cafe-medio">
                              {e.cliente.nombre} · {e.tipo_entrega === 'domicilio' ? 'Domicilio' : 'Recoge en el local'}
                            </span>
                          </span>
                          <span className="order-4 col-span-2 text-[17px] font-semibold whitespace-nowrap lg:order-3 lg:col-span-1">Saldo {pesos(e.saldo)}</span>
                          <span className="order-2 justify-self-end lg:order-4">
                            <Chip tono={ESTADOS_ENCARGO[e.estado].tono}>{ESTADOS_ENCARGO[e.estado].texto}</Chip>
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </Tarjeta>
            <div id="panel-detalle" className="scroll-mt-24">
              {encargo ? (
                <DetalleEncargo key={encargo.id} encargo={encargo} hoy={hoy} alEditar={() => setFormulario(encargo)} />
              ) : (
                <Tarjeta>
                  <p className="text-cafe-medio">Elige un encargo para ver su detalle, abonos y saldo.</p>
                </Tarjeta>
              )}
            </div>
          </div>
        </>
      )}

      {seccion === 'mes' && <Mes alElegirDia={(d) => fijar({ seccion: null, dia: d, encargo: null })} hoy={hoy} />}
      {seccion === 'domicilios' && <Domicilios />}
      {seccion === 'clientes' && <Clientes />}

      <DialogoEncargo
        abierto={formulario !== null}
        encargo={formulario === 'nuevo' ? null : formulario}
        diaInicial={dia < hoy ? hoy : dia}
        alCerrar={() => setFormulario(null)}
        alGuardar={(e) => {
          setFormulario(null)
          fijar({ seccion: null, dia: diaLocal(e.fecha_entrega), encargo: e.id })
        }}
      />
    </>
  )
}

/** Calendario mensual con el número de encargos por día (RF-39). */
function Mes({ alElegirDia, hoy }: { alElegirDia: (dia: string) => void; hoy: string }) {
  const [mes, setMes] = useState(() => primeroDelMes(hoy))
  const dias = diasDelMes(mes)
  const conteo = useQuery({
    queryKey: ['encargos', 'conteo', mes],
    queryFn: () => api<ConteoDia[]>(`/encargos/conteo?desde=${dias[0]}&hasta=${dias.at(-1)}`),
  })
  const por = new Map((conteo.data ?? []).map((c) => [c.fecha, c.encargos]))
  return (
    <Tarjeta className="px-5 py-6 lg:px-8">
      <div className="flex items-center justify-between gap-3">
        <button type="button" aria-label="Mes anterior" onClick={() => setMes(sumarMeses(mes, -1))} className="grid size-11 place-items-center rounded-control hover:bg-crema">
          <ChevronLeft aria-hidden className="size-6" />
        </button>
        <h2 className="font-serif text-[32px] font-medium first-letter:uppercase">{tituloMes(mes)}</h2>
        <button type="button" aria-label="Mes siguiente" onClick={() => setMes(sumarMeses(mes, 1))} className="grid size-11 place-items-center rounded-control hover:bg-crema">
          <ChevronRight aria-hidden className="size-6" />
        </button>
      </div>
      <div className="mt-4 grid grid-cols-7 gap-1.5 text-center lg:gap-2.5">
        {DIAS_CORTOS.map((d) => (
          <span key={d} className="pb-1 text-[13px] font-semibold tracking-[0.08em] text-cafe-suave uppercase">
            {d}
          </span>
        ))}
        {dias.map((d) => {
          const n = por.get(d) ?? 0
          const fuera = d.slice(0, 7) !== mes.slice(0, 7)
          return (
            <button
              key={d}
              type="button"
              aria-label={`${numeroDia(d)}: ${contar(n).toLowerCase()}`}
              onClick={() => alElegirDia(d)}
              className={unir(
                'flex h-[74px] flex-col items-center justify-center rounded-control border lg:h-[92px]',
                d === hoy ? 'border-2 border-fucsia bg-rosa-suave' : 'border-linea hover:border-dorado-borde',
                fuera && 'opacity-45',
                diaDeSemana(d) >= 5 && !fuera && d !== hoy && 'bg-crema',
              )}
            >
              <span className="font-serif text-[24px] leading-none font-medium">{numeroDia(d)}</span>
              {n > 0 && <span className="mt-1.5 rounded-full bg-fucsia px-2 text-[12px] font-bold text-white">{n}</span>}
            </button>
          )
        })}
      </div>
    </Tarjeta>
  )
}
