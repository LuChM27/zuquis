import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { CampoDinero } from '../../components/CampoDinero'
import { Dialogo } from '../../components/Dialogo'
import { AreaTexto, Aviso } from '../../components/formulario'
import { Boton } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api } from '../../lib/api'
import { unir } from '../../lib/clases'
import { pesos } from '../../lib/formato'
import { useClaveIdempotencia } from '../../lib/idempotencia'
import type { DecisionCancelacion, Encargo, FuenteGasto, MetodoPago } from '../../lib/tipos'
import { useSesion } from '../../auth/contexto'
import { Campo } from '../../components/ui'
import { FUENTES } from '../gastos/fuentes'
import { useCaja } from '../caja/usarCaja'
import { telefonoLegible, useMetodosActivos } from '../clientes/datos'
import { CamposDomicilio, type DatosDomicilio } from '../domicilios/CamposDomicilio'

/** Botones de método de pago (uno a la vez), como en el POS. */
function Metodos({ metodos, valor, alCambiar, etiqueta = 'Cómo paga' }: { metodos: MetodoPago[]; valor: string; alCambiar: (id: string) => void; etiqueta?: string }) {
  return (
    <div role="radiogroup" aria-label={etiqueta}>
      <p className="mb-1.5 text-sm font-semibold">{etiqueta}</p>
      <div className="flex flex-wrap gap-2">
        {metodos.map((m) => (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={valor === m.id}
            onClick={() => alCambiar(m.id)}
            className={unir(
              'h-11 rounded-control border px-4 text-[15px]',
              valor === m.id ? 'border-fucsia bg-rosa-suave font-semibold text-fucsia-oscuro' : 'border-dorado-claro bg-blanco hover:border-dorado-borde',
            )}
          >
            {m.nombre}
          </button>
        ))}
      </div>
    </div>
  )
}

/** Si la caja está cerrada no se recibe ni se devuelve dinero (RN-02). */
function RequiereCaja({ children }: { children: ReactNode }) {
  const caja = useCaja()
  if (caja.isPending) return <p className="text-cafe-medio">Revisando la caja…</p>
  if (!caja.data?.abierta)
    return (
      <Aviso tono="aviso">
        La caja está cerrada: ábrela en <Link to="/caja" className="font-semibold text-fucsia underline">Caja</Link> para recibir o devolver dinero.
      </Aviso>
    )
  return <>{children}</>
}

function useAccionEncargo<T>(ruta: string, alTerminar: (e: Encargo) => void, mensaje: (e: Encargo) => string) {
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const clave = useClaveIdempotencia()
  return useMutation({
    mutationFn: (cuerpo: T) => api<Encargo>(ruta, { method: 'POST', json: cuerpo, idempotencia: clave.para(cuerpo) }),
    onSuccess: (e) => {
      clave.olvidar()
      for (const k of [['encargos'], ['caja'], ['ventas'], ['domicilios'], ['productos'], ['clientes'], ['gastos']]) void clienteQuery.invalidateQueries({ queryKey: k })
      avisar(mensaje(e))
      alTerminar(e)
    },
  })
}

export function DialogoAbono({ encargo, abierto, alCerrar }: { encargo: Encargo; abierto: boolean; alCerrar: () => void }) {
  const metodos = useMetodosActivos()
  const [monto, setMonto] = useState<number | null>(null)
  const [metodo, setMetodo] = useState('')
  const abonar = useAccionEncargo<{ monto: number; metodo_pago_id: string }>(
    `/encargos/${encargo.id}/abonos`,
    () => {
      setMonto(null)
      alCerrar()
    },
    (e) => `Abono registrado. Saldo del encargo: ${pesos(e.saldo)}.`,
  )
  const excede = monto !== null && monto > encargo.saldo
  const listo = monto !== null && monto > 0 && !excede && metodo !== ''
  return (
    <Dialogo abierto={abierto} alCerrar={alCerrar} titulo="Registrar abono" rotulo={`Encargo n.º ${String(encargo.numero).padStart(4, '0')}`}>
      <RequiereCaja>
        <form
          noValidate
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (listo) abonar.mutate({ monto: monto!, metodo_pago_id: metodo })
          }}
        >
          <p className="text-cafe-medio">Saldo por cobrar: <strong>{pesos(encargo.saldo)}</strong></p>
          <CampoDinero etiqueta="Valor del abono" valor={monto} alCambiar={setMonto} error={excede ? 'El abono es mayor que el saldo.' : undefined} />
          <Metodos metodos={metodos.data ?? []} valor={metodo} alCambiar={setMetodo} />
          {abonar.isError && <Aviso>{abonar.error.message}</Aviso>}
          <Boton type="submit" disabled={!listo || abonar.isPending}>
            {abonar.isPending ? 'Registrando…' : monto ? `Registrar abono de ${pesos(monto)}` : 'Registrar abono'}
          </Boton>
        </form>
      </RequiereCaja>
    </Dialogo>
  )
}

/** Materiales comprados para decorar el encargo: queda como gasto de "Materiales de decoración"
 * ligado al encargo. Quien solo registra gastos de caja, solo desde la caja. */
export function DialogoGastoDecoracion({ encargo, abierto, alCerrar }: { encargo: Encargo; abierto: boolean; alCerrar: () => void }) {
  const { puede } = useSesion()
  const caja = useCaja()
  const metodos = useMetodosActivos()
  const soloCaja = !puede('gastos.crear')
  const [descripcion, setDescripcion] = useState('')
  const [monto, setMonto] = useState<number | null>(null)
  const [fuente, setFuente] = useState<FuenteGasto>('caja')
  const [metodoElegido, setMetodo] = useState('')
  const [intento, setIntento] = useState(false)
  // De la caja, por defecto en efectivo, como en Gastos.
  const metodo = metodoElegido || (fuente === 'caja' ? (metodos.data?.find((m) => m.es_efectivo)?.id ?? '') : '')
  const registrar = useAccionEncargo<{ descripcion: string; monto: number; metodo_pago_id: string; fuente: FuenteGasto }>(
    `/encargos/${encargo.id}/gastos`,
    () => {
      setDescripcion('')
      setMonto(null)
      setIntento(false)
      alCerrar()
    },
    () => 'Gasto de decoración registrado.',
  )
  const cajaCerrada = fuente === 'caja' && caja.data !== undefined && !caja.data.abierta
  const errores = {
    descripcion: descripcion.trim().length < 3 ? 'Escribe qué se compró (mínimo 3 letras).' : undefined,
    monto: !monto ? 'Escribe el valor.' : undefined,
    metodo: !metodo ? 'Elige cómo se pagó.' : undefined,
  }
  const listo = Object.values(errores).every((e) => !e) && !cajaCerrada
  return (
    <Dialogo abierto={abierto} alCerrar={alCerrar} titulo="Gasto de decoración" rotulo={`Encargo n.º ${String(encargo.numero).padStart(4, '0')}`}>
      <form
        noValidate
        className="grid gap-4"
        onSubmit={(e) => {
          e.preventDefault()
          setIntento(true)
          if (listo) registrar.mutate({ descripcion: descripcion.trim(), monto: monto!, metodo_pago_id: metodo, fuente })
        }}
      >
        <Campo
          etiqueta="Qué se compró"
          placeholder="Ej.: fondant, topper y letras"
          value={descripcion}
          maxLength={200}
          onChange={(e) => setDescripcion(e.target.value)}
          error={intento ? errores.descripcion : undefined}
        />
        <CampoDinero etiqueta="Valor" valor={monto} alCambiar={setMonto} error={intento ? errores.monto : undefined} />
        {!soloCaja && (
          <div role="radiogroup" aria-label="De dónde sale la plata">
            <p className="mb-1.5 text-sm font-semibold">De dónde sale la plata</p>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(FUENTES) as FuenteGasto[]).map((f) => (
                <button
                  key={f}
                  type="button"
                  role="radio"
                  aria-checked={fuente === f}
                  onClick={() => {
                    setFuente(f)
                    setMetodo('')
                  }}
                  className={unir(
                    'h-11 rounded-control border px-4 text-[15px]',
                    fuente === f ? 'border-fucsia bg-rosa-suave font-semibold text-fucsia-oscuro' : 'border-dorado-claro bg-blanco hover:border-dorado-borde',
                  )}
                >
                  {FUENTES[f].texto}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-sm text-cafe-medio">{FUENTES[fuente].ayuda}</p>
          </div>
        )}
        <Metodos metodos={metodos.data ?? []} valor={metodo} alCambiar={setMetodo} etiqueta="Cómo se pagó" />
        {intento && errores.metodo && <p role="alert" className="text-sm text-peligro-texto">{errores.metodo}</p>}
        {cajaCerrada && (
          <Aviso tono="aviso">
            La caja está cerrada: ábrela en <Link to="/caja" className="font-semibold text-fucsia underline">Caja</Link>
            {soloCaja ? ' para registrar el gasto.' : ' o elige otra forma de pago.'}
          </Aviso>
        )}
        {registrar.isError && <Aviso>{registrar.error.message}</Aviso>}
        <Boton type="submit" disabled={registrar.isPending || cajaCerrada || metodos.isPending}>
          {registrar.isPending ? 'Registrando…' : monto ? `Registrar gasto de ${pesos(monto)}` : 'Registrar gasto'}
        </Boton>
      </form>
    </Dialogo>
  )
}

export function DialogoEntrega({ encargo, abierto, alCerrar }: { encargo: Encargo; abierto: boolean; alCerrar: () => void }) {
  const metodos = useMetodosActivos()
  const aDomicilio = encargo.tipo_entrega === 'domicilio'
  const [metodo, setMetodo] = useState('')
  const [valorDomicilio, setValorDomicilio] = useState<number | null>(null)
  const [domicilio, setDomicilio] = useState<DatosDomicilio>({
    domiciliarioId: '',
    direccion: encargo.direccion_entrega ?? '',
    telefono: telefonoLegible(encargo.cliente.telefono),
  })
  const [intento, setIntento] = useState(false)
  const cobrar = encargo.saldo + (aDomicilio ? (valorDomicilio ?? 0) : 0)
  const entregar = useAccionEncargo<Record<string, unknown>>(
    `/encargos/${encargo.id}/entregar`,
    alCerrar,
    (e) => `Encargo entregado: venta n.º ${String(e.venta_numero).padStart(4, '0')}.`,
  )
  const faltaDomicilio = aDomicilio && (!domicilio.domiciliarioId || !domicilio.direccion.trim())
  const listo = !faltaDomicilio && (cobrar === 0 || metodo !== '')
  return (
    <Dialogo abierto={abierto} alCerrar={alCerrar} titulo="Entregar y cobrar" rotulo={`Encargo n.º ${String(encargo.numero).padStart(4, '0')}`}>
      <RequiereCaja>
        <form
          noValidate
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            setIntento(true)
            if (!listo) return
            entregar.mutate({
              pagos: cobrar > 0 ? [{ metodo_pago_id: metodo, monto: cobrar }] : [],
              valor_domicilio: aDomicilio ? (valorDomicilio ?? 0) : 0,
              domicilio: aDomicilio
                ? { domiciliario_id: domicilio.domiciliarioId, direccion: domicilio.direccion.trim(), telefono: domicilio.telefono.trim() || null }
                : null,
            })
          }}
        >
          <dl className="grid gap-1.5 text-[15px]">
            <div className="flex justify-between"><dt className="text-cafe-medio">Valor total</dt><dd>{pesos(encargo.total)}</dd></div>
            <div className="flex justify-between"><dt className="text-cafe-medio">Abonado</dt><dd>−{pesos(encargo.abonado)}</dd></div>
            <div className="flex justify-between font-semibold"><dt>Saldo</dt><dd>{pesos(encargo.saldo)}</dd></div>
          </dl>
          {aDomicilio && (
            <div className="grid gap-3 rounded-[14px] border border-linea p-4">
              <CamposDomicilio datos={domicilio} alCambiar={setDomicilio} intento={intento} />
              <CampoDinero etiqueta="Valor del domicilio" valor={valorDomicilio} alCambiar={setValorDomicilio} />
            </div>
          )}
          {cobrar > 0 ? (
            <Metodos metodos={metodos.data ?? []} valor={metodo} alCambiar={setMetodo} />
          ) : (
            <p className="text-cafe-medio">Ya está pagado con los abonos: no hay nada que cobrar.</p>
          )}
          {intento && cobrar > 0 && !metodo && <p role="alert" className="text-sm text-peligro-texto">Elige cómo paga.</p>}
          <p className="text-sm text-cafe-suave">Al entregar se registra la venta del encargo completo y se descuenta del inventario lo que sea de la carta.</p>
          {entregar.isError && <Aviso>{entregar.error.message}</Aviso>}
          <Boton type="submit" disabled={entregar.isPending}>
            {entregar.isPending ? 'Entregando…' : cobrar > 0 ? `Entregar y cobrar ${pesos(cobrar)}` : 'Entregar'}
          </Boton>
        </form>
      </RequiereCaja>
    </Dialogo>
  )
}

const DECISIONES: { valor: DecisionCancelacion; texto: string }[] = [
  { valor: 'devuelve_total', texto: 'Devolver todo lo abonado' },
  { valor: 'devuelve_parcial', texto: 'Devolver una parte' },
  { valor: 'retiene', texto: 'No devolver nada' },
]

/** RN-22: por defecto se devuelve todo; retener es una excepción con motivo. Solo administrador. */
export function DialogoCancelar({ encargo, abierto, alCerrar }: { encargo: Encargo; abierto: boolean; alCerrar: () => void }) {
  const metodos = useMetodosActivos()
  const [decision, setDecision] = useState<DecisionCancelacion>('devuelve_total')
  const [parcial, setParcial] = useState<number | null>(null)
  const [motivo, setMotivo] = useState('')
  const [metodo, setMetodo] = useState('')
  const [intento, setIntento] = useState(false)
  const cancelar = useAccionEncargo<Record<string, unknown>>(`/encargos/${encargo.id}/cancelar`, alCerrar, (e) =>
    e.monto_devuelto > 0 ? `Encargo cancelado. Se devolvieron ${pesos(e.monto_devuelto)}.` : 'Encargo cancelado.',
  )
  const abonado = encargo.abonado
  const devuelve = abonado === 0 ? 0 : decision === 'devuelve_total' ? abonado : decision === 'retiene' ? 0 : (parcial ?? 0)
  const parcialMal = decision === 'devuelve_parcial' && !(devuelve > 0 && devuelve < abonado)
  const sinMotivo = abonado > 0 && decision !== 'devuelve_total' && motivo.trim().length < 3
  const efectivo = metodos.data?.find((m) => m.es_efectivo)?.id ?? ''

  const formulario = (
    <form
      noValidate
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        setIntento(true)
        if (parcialMal || sinMotivo) return
        cancelar.mutate(
          abonado === 0
            ? {}
            : {
                decision,
                monto_devuelto: decision === 'devuelve_parcial' ? devuelve : null,
                motivo: motivo.trim() || null,
                metodo_pago_id: devuelve > 0 ? metodo || efectivo || null : null,
              },
        )
      }}
    >
      {abonado === 0 ? (
        <p className="text-cafe-medio">Este encargo no tiene abonos: solo se cancela.</p>
      ) : (
        <>
          <p className="text-cafe-medio">El cliente abonó <strong>{pesos(abonado)}</strong>. Lo normal es devolverlo todo.</p>
          <div role="radiogroup" aria-label="Qué pasa con el abono" className="grid gap-2">
            {DECISIONES.map((d) => (
              <label key={d.valor} className="flex cursor-pointer items-center gap-3 rounded-control border border-linea px-3.5 py-3">
                <input type="radio" name="decision" checked={decision === d.valor} onChange={() => setDecision(d.valor)} className="size-[18px] accent-fucsia" />
                <span>{d.texto}{d.valor === 'devuelve_total' && ` (${pesos(abonado)})`}</span>
              </label>
            ))}
          </div>
          {decision === 'devuelve_parcial' && (
            <CampoDinero
              etiqueta="Cuánto se devuelve"
              valor={parcial}
              alCambiar={setParcial}
              error={intento && parcialMal ? `Debe ser mayor que $0 y menor que ${pesos(abonado)}.` : undefined}
            />
          )}
          {decision !== 'devuelve_total' && (
            <>
              <AreaTexto etiqueta="Motivo" value={motivo} maxLength={200} onChange={(e) => setMotivo(e.target.value)} aria-invalid={intento && sinMotivo ? true : undefined} />
              {intento && sinMotivo && <p role="alert" className="text-sm text-peligro-texto">Escribe por qué no se devuelve todo.</p>}
              <p className="text-sm text-cafe-suave">Lo que no se devuelve ({pesos(abonado - devuelve)}) queda como ingreso por cancelación, no como venta.</p>
            </>
          )}
          {devuelve > 0 && <Metodos etiqueta="Con qué se devuelve" metodos={metodos.data ?? []} valor={metodo || efectivo} alCambiar={setMetodo} />}
        </>
      )}
      {cancelar.isError && <Aviso>{cancelar.error.message}</Aviso>}
      <Boton type="submit" variante="peligro" disabled={cancelar.isPending}>
        {cancelar.isPending ? 'Cancelando…' : devuelve > 0 ? `Cancelar y devolver ${pesos(devuelve)}` : 'Cancelar encargo'}
      </Boton>
    </form>
  )
  return (
    <Dialogo abierto={abierto} alCerrar={alCerrar} titulo="Cancelar encargo" rotulo={`Encargo n.º ${String(encargo.numero).padStart(4, '0')}`}>
      {devuelve > 0 ? <RequiereCaja>{formulario}</RequiereCaja> : formulario}
    </Dialogo>
  )
}

export function DialogoAnularAbono({
  encargo,
  abonoId,
  alCerrar,
}: {
  encargo: Encargo
  abonoId: string | null
  alCerrar: () => void
}) {
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const [motivo, setMotivo] = useState('')
  const abono = encargo.abonos.find((a) => a.id === abonoId)
  const anular = useMutation({
    mutationFn: () => api<Encargo>(`/encargos/${encargo.id}/abonos/${abonoId}/anular`, { method: 'POST', json: { motivo: motivo.trim() } }),
    onSuccess: () => {
      for (const k of [['encargos'], ['caja']]) void clienteQuery.invalidateQueries({ queryKey: k })
      avisar('Abono anulado.')
      setMotivo('')
      alCerrar()
    },
  })
  return (
    <Dialogo abierto={abonoId !== null} alCerrar={alCerrar} titulo="Anular abono">
      {abono && (
        <RequiereCaja>
          <form
            noValidate
            className="grid gap-4"
            onSubmit={(e) => {
              e.preventDefault()
              if (motivo.trim().length >= 3) anular.mutate()
            }}
          >
            <p className="text-cafe-medio">
              Los {pesos(abono.monto)} salen de la caja abierta de hoy por {abono.metodo}.
            </p>
            <AreaTexto etiqueta="Motivo" value={motivo} maxLength={200} onChange={(e) => setMotivo(e.target.value)} />
            {anular.isError && <Aviso>{anular.error.message}</Aviso>}
            <Boton type="submit" variante="peligro" disabled={anular.isPending || motivo.trim().length < 3}>
              {anular.isPending ? 'Anulando…' : 'Anular abono'}
            </Boton>
          </form>
        </RequiereCaja>
      )}
    </Dialogo>
  )
}
