import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CircleAlert } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { useSesion } from '../../auth/contexto'
import { Boton, Chip } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api } from '../../lib/api'
import { unir } from '../../lib/clases'
import { cantidad } from '../../lib/decimal'
import { fechaCorta, hora, pesos } from '../../lib/formato'
import type { Encargo, EstadoEncargo } from '../../lib/tipos'
import { DialogoAbono, DialogoAnularAbono, DialogoCancelar, DialogoEntrega, DialogoGastoDecoracion } from './Dialogos'
import { AVANZAR, ESTADOS_ENCARGO, PASOS } from './estados'
import { diaLocal, diaMesCorto, sumarDias } from './fechas'

const diaMes = (f: string) => diaMesCorto(diaLocal(f))

/** "entrega hoy 5:00 p. m.", "entrega mañana…", "entrega el 20/10/2026…" */
function cuando(fecha: string, hoy: string): string {
  const dia = diaLocal(fecha)
  const h = hora(new Date(fecha))
  if (dia === hoy) return `entrega hoy ${h}`
  if (dia === sumarDias(hoy, 1)) return `entrega mañana ${h}`
  return `entrega el ${fechaCorta(new Date(fecha))} ${h}`
}

/** Barra de cuatro segmentos del mockup: hechos en verde, el actual en fucsia. */
function Progreso({ estado }: { estado: EstadoEncargo }) {
  const actual = PASOS.indexOf(estado)
  return (
    <ol aria-label="Estado del encargo" className="grid grid-cols-4 gap-2">
      {PASOS.map((p, i) => {
        const hecho = estado === 'entregado' ? true : i < actual
        const esActual = i === actual && estado !== 'entregado'
        return (
          <li key={p} aria-current={esActual ? 'step' : undefined}>
            <span aria-hidden className={unir('block h-[7px] rounded-full', hecho ? 'bg-exito' : esActual ? 'bg-fucsia' : 'bg-pista')} />
            <span className={unir('mt-2 block text-[13px] leading-tight font-semibold', hecho ? 'text-exito-texto' : esActual ? 'text-fucsia-oscuro' : 'font-medium text-cafe-suave')}>
              {ESTADOS_ENCARGO[p].texto}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export function DetalleEncargo({ encargo: e, hoy, alEditar }: { encargo: Encargo; hoy: string; alEditar: () => void }) {
  const { puede } = useSesion()
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const [dialogo, setDialogo] = useState<'abono' | 'entrega' | 'cancelar' | 'gasto' | null>(null)
  const [anulando, setAnulando] = useState<string | null>(null)
  const activo = ['pendiente', 'en_produccion', 'listo'].includes(e.estado)
  const avanzar = AVANZAR[e.estado]
  const operador = puede('encargos.crear')
  const registraGastos = puede('gastos.crear') || puede('gastos.crear_caja')
  const conDecoracion = e.decoracion_cobrada > 0 || e.gastos_decoracion.length > 0

  const cambiar = useMutation({
    mutationFn: (estado: EstadoEncargo) => api<Encargo>(`/encargos/${e.id}/estado`, { method: 'POST', json: { estado } }),
    onSuccess: (x) => {
      void clienteQuery.invalidateQueries({ queryKey: ['encargos'] })
      avisar(`Encargo ${ESTADOS_ENCARGO[x.estado].texto.toLowerCase()}.`)
    },
    onError: (x) => avisar(x.message, 'error'),
  })

  const entrega = e.tipo_entrega === 'domicilio' ? `domicilio${e.direccion_entrega ? ` a ${e.direccion_entrega}` : ''}` : 'recoge en el local'
  const fila = 'flex items-baseline justify-between gap-3'

  return (
    <section aria-label={`Encargo n.º ${String(e.numero).padStart(4, '0')}`} className="rounded-tarjeta border-[1.5px] border-dorado-borde bg-blanco px-6 py-6 lg:px-[28px] lg:py-[30px]">
      <p className="text-[13px] font-semibold tracking-[0.12em] text-dorado-texto uppercase">Encargo n.º {String(e.numero).padStart(4, '0')}</p>
      <h2 className="mt-1 font-serif text-[34px] leading-[1.1] font-medium break-words">{e.descripcion}</h2>
      <p className="mt-2 text-[15px] text-cafe-medio">
        {e.cliente.nombre} · {cuando(e.fecha_entrega, hoy)} · {entrega}
      </p>

      {e.estado === 'cancelado' ? (
        <div className="mt-5"><Chip tono="peligro">Cancelado</Chip></div>
      ) : (
        <div className="mt-5"><Progreso estado={e.estado} /></div>
      )}

      {e.items.length > 1 || e.items[0]?.descripcion !== e.descripcion || e.decoracion_cobrada > 0 ? (
        <ul className="mt-5 grid gap-1 text-[15px] text-cafe-medio">
          {e.items.map((i) => (
            <li key={i.id}>
              <div className={fila}>
                <span>{cantidad(i.cantidad)} × {i.descripcion}</span>
                <span>{pesos(i.subtotal)}</span>
              </div>
              {i.decoracion && (
                <div className={unir(fila, 'pl-4 text-[14px]')}>
                  <span>Decoración: {i.decoracion}</span>
                  <span>{pesos(i.decoracion_precio ?? 0)}</span>
                </div>
              )}
            </li>
          ))}
        </ul>
      ) : null}
      {e.observaciones && <p className="mt-3 text-[15px] text-cafe-medio">Nota: {e.observaciones}</p>}

      <dl className="mt-5 grid gap-2.5 text-[17px]">
        <div className={fila}>
          <dt className="text-cafe-medio">Valor total</dt>
          <dd className="font-semibold">{pesos(e.total)}</dd>
        </div>
        {e.abonos.map((a) => (
          <div key={a.id} className={fila}>
            <dt className={unir('text-cafe-medio', a.estado === 'anulado' && 'line-through')}>
              Abono {diaMes(a.fecha)} · {a.metodo}
              {a.estado === 'vigente' && activo && puede('encargos.anular_abono') && (
                <button type="button" onClick={() => setAnulando(a.id)} className="ml-2 text-sm text-fucsia underline">
                  Anular
                </button>
              )}
            </dt>
            <dd className={unir('whitespace-nowrap text-cafe-medio', a.estado === 'anulado' && 'line-through')}>−{pesos(a.monto)}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-3 border-t border-linea pt-4">
        {e.estado === 'entregado' ? (
          <p className="text-[15px] text-cafe-medio">
            Entregado y cobrado.{' '}
            {e.venta_numero && (
              <Link to={`/ventas?numero=${e.venta_numero}`} className="font-semibold text-fucsia underline">
                Venta n.º {String(e.venta_numero).padStart(4, '0')}
              </Link>
            )}
          </p>
        ) : e.estado === 'cancelado' ? (
          <p className="text-[15px] text-cafe-medio">
            {e.monto_devuelto > 0 && `Se devolvieron ${pesos(e.monto_devuelto)}. `}
            {e.monto_retenido > 0 && `Se retuvieron ${pesos(e.monto_retenido)} (ingreso por cancelación). `}
            {e.motivo_cancelacion && `Motivo: ${e.motivo_cancelacion}`}
          </p>
        ) : (
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-[17px] font-semibold">Saldo por cobrar</span>
            <span className="font-serif text-[44px] leading-none font-medium">{pesos(e.saldo)}</span>
          </div>
        )}
      </div>

      {conDecoracion && (
        <section aria-label="Decoración" className="mt-5 rounded-[14px] border border-linea px-4 py-4">
          <h3 className="text-[13px] font-semibold tracking-[0.12em] text-dorado-texto uppercase">Decoración</h3>
          <dl className="mt-2 grid gap-1.5 text-[16px]">
            <div className={fila}>
              <dt className="text-cafe-medio">Cobrado</dt>
              <dd>{pesos(e.decoracion_cobrada)}</dd>
            </div>
            <div className={fila}>
              <dt className="text-cafe-medio">Gastado en materiales</dt>
              <dd>−{pesos(e.gasto_decoracion)}</dd>
            </div>
            <div className={unir(fila, 'border-t border-linea pt-1.5 font-semibold')}>
              <dt>Diferencia</dt>
              <dd className={e.decoracion_cobrada - e.gasto_decoracion < 0 ? 'text-peligro-texto' : undefined}>{pesos(e.decoracion_cobrada - e.gasto_decoracion)}</dd>
            </div>
          </dl>
          {e.gastos_decoracion.reduce((s, g) => s + (g.estado === 'registrado' ? g.monto : 0), 0) < e.gasto_decoracion && (
            <p className="mt-3 text-[14px] text-cafe-medio">Incluye gastos registrados por la administración.</p>
          )}
          {e.gastos_decoracion.length > 0 && (
            <ul className="mt-3 grid gap-1 text-[14px] text-cafe-medio">
              {e.gastos_decoracion.map((g) => (
                <li key={g.id} className={unir(fila, g.estado === 'anulado' && 'line-through')}>
                  <span>
                    {diaMesCorto(g.fecha)} · {g.descripcion}
                  </span>
                  <span>{pesos(g.monto)}</span>
                </li>
              ))}
            </ul>
          )}
          {registraGastos && (
            <Boton variante="secundario" className="mt-3 h-11 w-full" onClick={() => setDialogo('gasto')}>
              Registrar gasto de decoración
            </Boton>
          )}
        </section>
      )}

      {(e.estado === 'en_produccion' || e.estado === 'listo') && (
        <p role="status" className="mt-5 flex gap-3 rounded-[14px] bg-aviso-fondo px-4 py-4 text-[15px] text-cafe-medio">
          <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-aviso" />
          Ya pasó a producción, así que no se puede editar. Solo un administrador puede cancelarlo.
        </p>
      )}

      {activo && operador && (
        <div className="mt-5 grid gap-3">
          {e.estado === 'listo' ? (
            <button type="button" onClick={() => setDialogo('entrega')} className="h-[58px] rounded-[16px] bg-fucsia text-[18px] font-bold text-white hover:bg-fucsia-oscuro">
              {e.saldo > 0 ? `Entregar y cobrar ${pesos(e.saldo)}` : 'Entregar'}
            </button>
          ) : (
            avanzar && (
              <button
                type="button"
                disabled={cambiar.isPending}
                onClick={() => cambiar.mutate(avanzar.a)}
                className="h-[58px] rounded-[16px] bg-fucsia text-[18px] font-bold text-white hover:bg-fucsia-oscuro disabled:opacity-60"
              >
                {avanzar.texto}
              </button>
            )
          )}
          {e.saldo > 0 && (
            <Boton variante="secundario" className="h-[52px]" onClick={() => setDialogo('abono')}>
              {e.abonos.some((a) => a.estado === 'vigente') ? 'Registrar otro abono' : 'Registrar abono'}
            </Boton>
          )}
          {e.editable && (
            <Boton variante="secundario" className="h-[52px]" onClick={alEditar}>
              Editar encargo
            </Boton>
          )}
        </div>
      )}
      {activo && puede('encargos.devolver_abono') && (
        <button type="button" onClick={() => setDialogo('cancelar')} className="mt-4 text-[15px] font-semibold text-peligro-texto underline">
          Cancelar encargo
        </button>
      )}

      <DialogoAbono encargo={e} abierto={dialogo === 'abono'} alCerrar={() => setDialogo(null)} />
      {dialogo === 'entrega' && <DialogoEntrega encargo={e} abierto alCerrar={() => setDialogo(null)} />}
      {dialogo === 'gasto' && <DialogoGastoDecoracion encargo={e} abierto alCerrar={() => setDialogo(null)} />}
      {dialogo === 'cancelar' && <DialogoCancelar encargo={e} abierto alCerrar={() => setDialogo(null)} />}
      <DialogoAnularAbono encargo={e} abonoId={anulando} alCerrar={() => setAnulando(null)} />
    </section>
  )
}
