import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDownToLine, ArrowUpFromLine } from 'lucide-react'
import { useRef, useState } from 'react'
import { useSesion } from '../../auth/contexto'
import { CampoDinero } from '../../components/CampoDinero'
import { Dialogo } from '../../components/Dialogo'
import { Celda, Selector, Tabla, Vacio } from '../../components/formulario'
import { Boton, Campo, Tarjeta, TituloTarjeta } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api } from '../../lib/api'
import { unir } from '../../lib/clases'
import { hora, pesos } from '../../lib/formato'
import type { MetodoPago, MovimientoCaja } from '../../lib/tipos'
import { FormAbrirCaja } from './AbrirCaja'
import { TIPOS_MOVIMIENTO } from './textos'
import { useCaja } from './usarCaja'

export function CajaHoy({ alCerrar }: { alCerrar: () => void }) {
  const { puede } = useSesion()
  const caja = useCaja()
  const movimientos = useQuery({
    queryKey: ['caja', 'movimientos'],
    queryFn: () => api<MovimientoCaja[]>('/caja/actual/movimientos'),
    enabled: !!caja.data?.abierta,
  })
  const [manual, setManual] = useState<'entrada_manual' | 'salida_manual' | null>(null)

  if (caja.isPending) return <p className="text-cafe-medio">Cargando…</p>
  if (!caja.data?.abierta || !caja.data.sesion) {
    return (
      <Tarjeta className="max-w-[460px] p-7">
        <TituloTarjeta>La caja está cerrada</TituloTarjeta>
        {puede('caja.abrir') ? (
          <div className="mt-4 grid gap-4">
            <p className="text-cafe-medio">Ábrela con el efectivo con el que arranca el turno. Sin caja abierta no se vende.</p>
            <FormAbrirCaja />
          </div>
        ) : (
          <p className="mt-4 text-cafe-medio">Pide a quien abre la caja que la abra.</p>
        )}
      </Tarjeta>
    )
  }

  const sesion = caja.data.sesion
  const lista = [...(movimientos.data ?? [])].reverse()
  return (
    <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Tarjeta>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <TituloTarjeta>Movimientos del turno</TituloTarjeta>
          {puede('caja.movimientos') && (
            <div className="flex flex-wrap gap-2">
              <Boton variante="secundario" className="h-11 px-4 text-[15px]" onClick={() => setManual('entrada_manual')}>
                <ArrowDownToLine aria-hidden className="size-[18px]" />
                Entrada
              </Boton>
              <Boton variante="secundario" className="h-11 px-4 text-[15px]" onClick={() => setManual('salida_manual')}>
                <ArrowUpFromLine aria-hidden className="size-[18px]" />
                Salida
              </Boton>
            </div>
          )}
        </div>
        <div className="mt-4">
          {lista.length === 0 ? (
            <Vacio>Todavía no hay movimientos: las ventas, gastos y pagos que salgan de la caja aparecen aquí.</Vacio>
          ) : (
            <Tabla
              columnas={[
                { texto: 'Hora' },
                { texto: 'Movimiento' },
                { texto: 'Método', ocultarMovil: true },
                { texto: 'Valor', derecha: true },
              ]}
            >
              {lista.map((m) => (
                <tr key={m.id} className="border-b border-linea last:border-b-0">
                  <Celda className="whitespace-nowrap text-cafe-medio">{hora(new Date(m.fecha))}</Celda>
                  <Celda>
                    <span className="block font-medium">{TIPOS_MOVIMIENTO[m.tipo] ?? m.tipo}</span>
                    {(m.motivo || m.usuario) && (
                      <span className="block text-sm text-cafe-suave">{[m.motivo, m.usuario].filter(Boolean).join(' · ')}</span>
                    )}
                  </Celda>
                  <Celda ocultarMovil>{m.metodo}</Celda>
                  <Celda derecha className={unir('font-semibold whitespace-nowrap', m.monto < 0 && 'text-peligro-texto')}>
                    {pesos(m.monto, { signo: true })}
                  </Celda>
                </tr>
              ))}
            </Tabla>
          )}
        </div>
      </Tarjeta>

      <Tarjeta>
        <TituloTarjeta>Debería haber ahora</TituloTarjeta>
        <p className="mt-1 text-sm text-cafe-suave">
          Abierta {hora(new Date(sesion.abierta_en))}
          {sesion.responsable && ` por ${sesion.responsable}`} · base {pesos(sesion.base_inicial)}
        </p>
        <dl className="mt-4 grid gap-2.5">
          {caja.data.esperado.map((e) => (
            <div key={e.metodo_pago_id} className="flex items-baseline justify-between gap-3">
              <dt>{e.metodo}</dt>
              <dd className="font-semibold">{pesos(e.esperado)}</dd>
            </div>
          ))}
        </dl>
        {puede('caja.cerrar') && (
          <Boton className="mt-5 w-full" onClick={alCerrar}>
            Ir al cierre de caja
          </Boton>
        )}
      </Tarjeta>

      <DialogoMovimiento tipo={manual} alCerrar={() => setManual(null)} />
    </div>
  )
}

function DialogoMovimiento({ tipo, alCerrar }: { tipo: 'entrada_manual' | 'salida_manual' | null; alCerrar: () => void }) {
  return (
    <Dialogo
      abierto={tipo !== null}
      alCerrar={alCerrar}
      titulo={tipo === 'salida_manual' ? 'Salida de dinero' : 'Entrada de dinero'}
      rotulo="Movimiento manual"
    >
      {tipo && <FormMovimiento tipo={tipo} alCerrar={alCerrar} />}
    </Dialogo>
  )
}

function FormMovimiento({ tipo, alCerrar }: { tipo: 'entrada_manual' | 'salida_manual'; alCerrar: () => void }) {
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const metodos = useQuery({ queryKey: ['metodos-pago'], queryFn: () => api<MetodoPago[]>('/metodos-pago') })
  const [metodoElegido, setMetodo] = useState('')
  const [monto, setMonto] = useState<number | null>(null)
  const [motivo, setMotivo] = useState('')
  const [intento, setIntento] = useState(false)
  const clave = useRef(crypto.randomUUID())
  const metodoId = metodoElegido || metodos.data?.find((m) => m.es_efectivo)?.id || ''
  const guardar = useMutation({
    mutationFn: () =>
      api('/caja/movimientos', {
        method: 'POST',
        idempotencia: clave.current,
        json: { tipo, metodo_pago_id: metodoId, monto, motivo: motivo.trim() },
      }),
    onSuccess: () => {
      avisar(tipo === 'salida_manual' ? 'Salida registrada.' : 'Entrada registrada.')
      void clienteQuery.invalidateQueries({ queryKey: ['caja'] })
      alCerrar()
    },
    onError: (e) => avisar(e.message, 'error'),
  })
  const errores = {
    monto: !monto ? 'Escribe el valor.' : undefined,
    motivo: motivo.trim().length < 3 ? 'Escribe el motivo (mínimo 3 letras).' : undefined,
  }
  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        setIntento(true)
        if (!errores.monto && !errores.motivo && metodoId) guardar.mutate()
      }}
    >
      <p className="text-sm text-cafe-medio">
        {tipo === 'salida_manual'
          ? 'Dinero que sale de la caja sin ser gasto ni pago (por ejemplo, se lleva a consignar).'
          : 'Dinero que entra a la caja sin ser venta (por ejemplo, más sencillo para el cambio).'}
      </p>
      <Selector etiqueta="Método" value={metodoId} onChange={(e) => setMetodo(e.target.value)}>
        {metodos.data?.map((m) => (
          <option key={m.id} value={m.id}>
            {m.nombre}
          </option>
        ))}
      </Selector>
      <CampoDinero etiqueta="Valor" valor={monto} alCambiar={setMonto} error={intento ? errores.monto : undefined} />
      <Campo
        etiqueta="Motivo"
        value={motivo}
        maxLength={200}
        onChange={(e) => setMotivo(e.target.value)}
        error={intento ? errores.motivo : undefined}
      />
      <Boton type="submit" disabled={guardar.isPending}>
        {guardar.isPending ? 'Registrando…' : 'Registrar'}
      </Boton>
    </form>
  )
}
