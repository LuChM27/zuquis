import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Aviso, AreaTexto, Selector } from '../../components/formulario'
import { Boton, Campo } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api, ErrorApi } from '../../lib/api'
import { dec } from '../../lib/decimal'
import { pesos } from '../../lib/formato'
import type { Ajuste, Lote, Merma, MotivoMerma, StockItem } from '../../lib/tipos'
import { cantidadLegible, fechaDiaMes } from '../../lib/unidades'
import { mensajeDeError } from '../configuracion/acciones'
import { leerCantidad, MOTIVOS, rutaItem } from './comun'

/** Lo que cambia tras una merma o un ajuste. */
function useRefrescar() {
  const cliente = useQueryClient()
  return () => cliente.invalidateQueries({ queryKey: ['inventario'] })
}

/** "= 2,5 kg" debajo del campo, para confirmar lo escrito en la unidad base. */
function Equivale({ texto, unidad }: { texto: string; unidad: string }) {
  const valor = leerCantidad(texto)
  if (!valor || unidad === 'und' || dec(valor).lt(1000)) return null
  return <p className="mt-1.5 text-sm text-cafe-suave">= {cantidadLegible(valor, unidad)}</p>
}

export function FormMerma({
  items,
  inicial,
  hoy,
  alTerminar,
}: {
  items: StockItem[]
  inicial?: StockItem
  hoy: string
  alTerminar: () => void
}) {
  const { avisar } = useAvisos()
  const refrescar = useRefrescar()
  const [itemId, setItemId] = useState(inicial?.item_id ?? '')
  const [loteId, setLoteId] = useState('')
  const [cantidad, setCantidad] = useState('')
  const [motivo, setMotivo] = useState<MotivoMerma>('danado')
  const [nota, setNota] = useState('')
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [error, setError] = useState<string>()
  const [enviando, setEnviando] = useState(false)
  const [clave] = useState(() => crypto.randomUUID())
  const item = items.find((i) => i.item_id === itemId)
  const lotes = useQuery({
    queryKey: ['inventario', 'lotes', itemId],
    queryFn: () => api<Lote[]>(`${rutaItem(item!)}/lotes`),
    enabled: !!item,
  })

  async function enviar(ev: FormEvent) {
    ev.preventDefault()
    const e: Record<string, string> = {}
    const valor = leerCantidad(cantidad)
    if (!item) e.item = 'Elige el insumo o producto.'
    if (!valor || dec(valor).lte(0)) e.cantidad = 'Escribe la cantidad, por ejemplo 250 o 2,5.'
    setErrores(e)
    if (Object.keys(e).length || !item || !valor) return
    setEnviando(true)
    setError(undefined)
    try {
      const merma = await api<Merma>('/mermas', {
        method: 'POST',
        idempotencia: clave,
        json: {
          tipo_item: item.tipo_item,
          item_id: item.item_id,
          lote_id: loteId || null,
          cantidad: valor,
          motivo,
          nota: nota.trim() || null,
        },
      })
      await refrescar()
      avisar(`Merma registrada: ${cantidadLegible(merma.cantidad, item.unidad)} de ${item.nombre} (${pesos(-merma.costo_total)}).`)
      alTerminar()
    } catch (err) {
      setError(
        err instanceof ErrorApi && err.codigo === 'STOCK_INSUFICIENTE'
          ? `No hay tanto ${item.nombre.toLowerCase()}: quedan ${cantidadLegible(String(err.detalle.disponible ?? '0'), item.unidad)}${loteId ? ' en ese lote' : ''}.`
          : mensajeDeError(err),
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
      <Selector
        etiqueta="Insumo o producto"
        value={itemId}
        onChange={(e) => {
          setItemId(e.target.value)
          setLoteId('')
        }}
        aria-invalid={errores.item ? true : undefined}
      >
        <option value="" disabled>
          Elige uno
        </option>
        {items.map((i) => (
          <option key={i.item_id} value={i.item_id}>
            {i.nombre}
          </option>
        ))}
      </Selector>
      {errores.item && <p className="-mt-2.5 text-sm text-peligro-texto">{errores.item}</p>}
      {item && (
        <Selector etiqueta="De qué lote" value={loteId} onChange={(e) => setLoteId(e.target.value)}>
          <option value="">El más antiguo primero (PEPS)</option>
          {lotes.data?.map((l) => (
            <option key={l.id} value={l.id}>
              {l.vencido ? 'Vencido · ' : ''}
              {cantidadLegible(l.cantidad_disponible, item.unidad)}
              {l.fecha_vencimiento ? ` · vence ${fechaDiaMes(l.fecha_vencimiento, hoy)}` : ''}
            </option>
          ))}
        </Selector>
      )}
      <div>
        <Campo
          etiqueta={`Cantidad${item ? ` (${item.unidad})` : ''}`}
          inputMode="decimal"
          value={cantidad}
          onChange={(e) => setCantidad(e.target.value)}
          error={errores.cantidad}
        />
        {item && <Equivale texto={cantidad} unidad={item.unidad} />}
      </div>
      <Selector etiqueta="Motivo" value={motivo} onChange={(e) => setMotivo(e.target.value as MotivoMerma)}>
        {Object.entries(MOTIVOS).map(([v, t]) => (
          <option key={v} value={v}>
            {t}
          </option>
        ))}
      </Selector>
      <AreaTexto etiqueta="Nota (opcional)" value={nota} maxLength={200} onChange={(e) => setNota(e.target.value)} />
      {error && <Aviso>{error}</Aviso>}
      <Boton type="submit" disabled={enviando}>
        {enviando ? 'Registrando…' : 'Registrar merma'}
      </Boton>
    </form>
  )
}

export function FormAjuste({ item, alTerminar }: { item: StockItem; alTerminar: () => void }) {
  const { avisar } = useAvisos()
  const refrescar = useRefrescar()
  const [contada, setContada] = useState('')
  const [motivo, setMotivo] = useState('Conteo físico')
  const [costo, setCosto] = useState('')
  const [pideCosto, setPideCosto] = useState(false)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [error, setError] = useState<string>()
  const [enviando, setEnviando] = useState(false)
  const [clave, setClave] = useState(() => crypto.randomUUID())
  const vencido = dec(item.cantidad_vencida).gt(0)

  async function enviar(ev: FormEvent) {
    ev.preventDefault()
    const e: Record<string, string> = {}
    const valor = leerCantidad(contada)
    const costoUnitario = leerCantidad(costo)
    if (!valor) e.contada = 'Escribe lo que contaste, por ejemplo 2500 o 0.'
    if (motivo.trim().length < 3) e.motivo = 'Cuenta en pocas palabras por qué (mínimo 3 letras).'
    if (pideCosto && costoUnitario === null) e.costo = 'Escribe cuánto cuesta cada unidad.'
    setErrores(e)
    if (Object.keys(e).length || !valor) return
    setEnviando(true)
    setError(undefined)
    try {
      const ajuste = await api<Ajuste>('/ajustes', {
        method: 'POST',
        idempotencia: clave,
        json: {
          tipo_item: item.tipo_item,
          item_id: item.item_id,
          cantidad_contada: valor,
          motivo: motivo.trim(),
          costo_unitario: pideCosto ? costoUnitario : null,
        },
      })
      await refrescar()
      const dif = dec(ajuste.diferencia)
      avisar(
        `Ajuste registrado: ${dif.isNegative() ? 'faltaban' : 'sobraban'} ${cantidadLegible(dif.abs().toFixed(), item.unidad)} (${pesos(ajuste.costo_total, { signo: true })}).`,
      )
      alTerminar()
    } catch (err) {
      if (err instanceof ErrorApi && err.codigo === 'COSTO_REQUERIDO') {
        setPideCosto(true)
        // Es otra petición (con costo): necesita su propia clave de idempotencia.
        setClave(crypto.randomUUID())
      }
      setError(mensajeDeError(err))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
      <p className="text-cafe-medio">
        El sistema tiene <strong className="text-cafe">{cantidadLegible(item.cantidad, item.unidad)}</strong> de{' '}
        {item.nombre.toLowerCase()}. Si cuentas otra cantidad, la diferencia se registra como ajuste.
      </p>
      {vencido && (
        <Aviso tono="aviso">
          Además hay {cantidadLegible(item.cantidad_vencida, item.unidad)} vencido. No lo cuentes: regístralo como
          merma para darlo de baja.
        </Aviso>
      )}
      <div>
        <Campo
          etiqueta={`Cantidad contada (${item.unidad})`}
          inputMode="decimal"
          value={contada}
          onChange={(e) => setContada(e.target.value)}
          error={errores.contada}
        />
        <Equivale texto={contada} unidad={item.unidad} />
      </div>
      <Campo etiqueta="Motivo" value={motivo} maxLength={200} onChange={(e) => setMotivo(e.target.value)} error={errores.motivo} />
      {pideCosto && (
        <Campo
          etiqueta={`Costo por ${item.unidad} (en pesos, admite decimales)`}
          inputMode="decimal"
          value={costo}
          onChange={(e) => setCosto(e.target.value)}
          error={errores.costo}
        />
      )}
      {error && <Aviso>{error}</Aviso>}
      <Boton type="submit" disabled={enviando}>
        {enviando ? 'Registrando…' : 'Registrar ajuste'}
      </Boton>
    </form>
  )
}
