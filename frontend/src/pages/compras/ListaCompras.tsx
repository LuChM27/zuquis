import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useSesion } from '../../auth/contexto'
import { CampoDinero } from '../../components/CampoDinero'
import { Dialogo } from '../../components/Dialogo'
import { AreaTexto, Aviso, Celda, FilaTabla, ListaDetalle, PanelDetalle, Selector, Tabla, Vacio } from '../../components/formulario'
import { Boton, Chip } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api } from '../../lib/api'
import { fechaCorta, hora, pesos } from '../../lib/formato'
import type { Compra, EstadoPago, MetodoPago, Pagina } from '../../lib/tipos'
import { cantidad as textoCantidad } from '../../lib/decimal'
import { cantidadLegible, costoPorUnidad, fechaDiaMes, fechaIso, hoyIso } from '../../lib/unidades'
import { mensajeDeError } from '../configuracion/acciones'
import { TarjetaLista } from '../configuracion/comun'
import { useImagen } from '../carta/utilidades'
import { SaleDeCaja } from '../caja/SaleDeCaja'
import { useCaja, usarDesdeCaja } from '../caja/usarCaja'

const TAMANO = 50

export function EstadoCompra({ compra }: { compra: Pick<Compra, 'anulada' | 'estado_pago'> }) {
  if (compra.anulada) return <Chip>Anulada</Chip>
  if (compra.estado_pago === 'por_pagar') return <Chip tono="aviso">Por pagar</Chip>
  return <Chip tono="exito">{compra.estado_pago === 'contado' ? 'De contado' : 'Pagada'}</Chip>
}

export function ListaCompras({ elegida, alElegir }: { elegida?: string; alElegir: (id: string) => void }) {
  const [pagina, setPagina] = useState(1)
  const [estado, setEstado] = useState<EstadoPago | ''>('')
  const compras = useQuery({
    queryKey: ['compras', 'lista', pagina, estado],
    queryFn: () => api<Pagina<Compra>>(`/compras?page=${pagina}&size=${TAMANO}${estado ? `&estado_pago=${estado}` : ''}`),
    placeholderData: keepPreviousData,
  })
  const lista = compras.data?.items ?? []
  const actualId = elegida ?? lista[0]?.id
  const paginas = Math.max(1, Math.ceil((compras.data?.total ?? 0) / TAMANO))

  return (
    <ListaDetalle
      lista={
        <TarjetaLista titulo="Compras">
          <Selector
            etiqueta="Estado del pago"
            value={estado}
            onChange={(e) => {
              setEstado(e.target.value as EstadoPago | '')
              setPagina(1)
            }}
            className="mb-4 max-w-xs"
          >
            <option value="">Todas</option>
            <option value="por_pagar">Por pagar</option>
            <option value="pagada">Pagadas</option>
            <option value="contado">De contado</option>
          </Selector>
          {compras.isError && <Aviso>No pudimos cargar las compras. Recarga la página para intentarlo de nuevo.</Aviso>}
          {compras.isSuccess && lista.length === 0 && <Vacio>No hay compras con este filtro.</Vacio>}
          {lista.length > 0 && (
            <Tabla
              columnas={[
                { texto: 'Fecha' },
                { texto: 'Proveedor' },
                { texto: 'Total', derecha: true },
                { texto: 'Saldo', derecha: true, ocultarMovil: true },
                { texto: 'Estado' },
              ]}
            >
              {lista.map((c) => (
                <FilaTabla key={c.id} seleccionada={c.id === actualId} alElegir={() => alElegir(c.id)}>
                  <Celda className="whitespace-nowrap">{fechaIso(c.fecha)}</Celda>
                  <Celda>
                    <span className="block font-semibold">{c.proveedor ?? 'Sin proveedor'}</span>
                    <span className="block text-sm text-cafe-suave">
                      {c.items.map((i) => i.insumo).join(', ')}
                    </span>
                  </Celda>
                  <Celda derecha className="font-semibold whitespace-nowrap">{pesos(c.total)}</Celda>
                  <Celda derecha ocultarMovil className="whitespace-nowrap">{c.saldo > 0 && !c.anulada ? pesos(c.saldo) : '—'}</Celda>
                  <Celda>
                    <EstadoCompra compra={c} />
                  </Celda>
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
        </TarjetaLista>
      }
      detalle={actualId ? <DetalleCompra key={actualId} id={actualId} /> : null}
    />
  )
}

export function DetalleCompra({ id }: { id: string }) {
  const { puede } = useSesion()
  const compra = useQuery({ queryKey: ['compras', 'detalle', id], queryFn: () => api<Compra>(`/compras/${id}`) })
  const [anulando, setAnulando] = useState(false)
  const [viendoSoporte, setViendoSoporte] = useState(false)
  const c = compra.data
  if (compra.isError) return <Aviso>No pudimos cargar la compra.</Aviso>
  if (!c) return null
  const creada = new Date(c.creado_en)
  const hoy = hoyIso()
  return (
    <PanelDetalle
      rotulo={`Compra del ${fechaIso(c.fecha)}`}
      titulo={c.proveedor ?? 'Sin proveedor'}
      subtitulo={`${c.numero_factura_proveedor ? `Factura ${c.numero_factura_proveedor} · ` : ''}registrada ${fechaCorta(creada)} ${hora(creada)}`}
    >
      <div className="mb-4 flex flex-wrap gap-2">
        <EstadoCompra compra={c} />
      </div>
      {c.anulada && <Aviso tono="aviso">Anulada: {c.motivo_anulacion}. Sus lotes salieron del inventario.</Aviso>}
      <ul aria-label="Insumos de la compra" className="flex flex-col divide-y divide-linea">
        {c.items.map((i) => (
          <li key={i.id} className="py-2.5">
            <p className="flex justify-between gap-3">
              <span className="font-semibold">{i.insumo}</span>
              <span className="font-semibold">{pesos(i.costo_total)}</span>
            </p>
            <p className="text-sm text-cafe-medio">
              {i.presentacion ? `${textoCantidad(i.cantidad)} × ${i.presentacion} = ` : ''}
              {cantidadLegible(i.cantidad_base, i.unidad)} a {costoPorUnidad(i.costo_unitario, i.unidad)}
              {i.fecha_vencimiento && ` · vence ${fechaDiaMes(i.fecha_vencimiento, hoy)}`}
            </p>
          </li>
        ))}
      </ul>
      <dl className="mt-3 border-t border-dorado-claro pt-3">
        <div className="flex justify-between gap-3 py-1">
          <dt className="font-semibold">Total</dt>
          <dd className="font-semibold">{pesos(c.total)}</dd>
        </div>
        {c.estado_pago !== 'contado' && (
          <>
            <div className="flex justify-between gap-3 py-1 text-cafe-medio">
              <dt>Pagado</dt>
              <dd>{pesos(c.pagado)}</dd>
            </div>
            <div className="flex justify-between gap-3 py-1">
              <dt className="font-semibold">Saldo</dt>
              <dd className={c.saldo > 0 ? 'font-semibold text-peligro-texto' : 'font-semibold'}>{pesos(c.saldo)}</dd>
            </div>
          </>
        )}
      </dl>
      {c.pagos.length > 0 && (
        <section aria-label="Pagos" className="mt-4">
          <h3 className="text-sm font-semibold">Pagos</h3>
          <ul className="mt-1.5 text-sm text-cafe-medio">
            {c.pagos.map((p) => (
              <li key={p.id} className="flex justify-between gap-3 py-1">
                <span>
                  {fechaCorta(new Date(p.fecha))} · {p.metodo_pago}
                </span>
                <span>{pesos(p.monto)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {!c.anulada && c.estado_pago === 'por_pagar' && puede('compras.crear') && <FormPago compra={c} />}
      <div className="mt-5 flex flex-col gap-2.5">
        {c.soporte_url && (
          <Boton variante="secundario" onClick={() => setViendoSoporte(true)}>
            Ver soporte
          </Boton>
        )}
        {!c.anulada && puede('compras.anular') && (
          <Boton variante="peligro" onClick={() => setAnulando(true)}>
            Anular compra
          </Boton>
        )}
      </div>
      <Dialogo abierto={anulando} alCerrar={() => setAnulando(false)} titulo="Anular compra">
        {anulando && <FormAnular compra={c} alTerminar={() => setAnulando(false)} />}
      </Dialogo>
      <Dialogo forma="ancho" abierto={viendoSoporte} alCerrar={() => setViendoSoporte(false)} rotulo="Soporte" titulo={c.proveedor ?? 'Compra'}>
        {viendoSoporte && c.soporte_url && <Soporte url={c.soporte_url} />}
      </Dialogo>
    </PanelDetalle>
  )
}

function Soporte({ url }: { url: string }) {
  const imagen = useImagen(url)
  if (!imagen) return <p className="text-cafe-medio">Cargando la foto…</p>
  return <img src={imagen} alt="Foto de la factura" className="max-h-[70dvh] w-full rounded-control object-contain" />
}

function FormPago({ compra }: { compra: Compra }) {
  const cliente = useQueryClient()
  const { avisar } = useAvisos()
  const metodos = useQuery({ queryKey: ['metodos-pago'], queryFn: () => api<MetodoPago[]>('/metodos-pago') })
  const [monto, setMonto] = useState<number | null>(compra.saldo)
  const [metodoElegido, setMetodo] = useState('')
  const [error, setError] = useState<string>()
  const [enviando, setEnviando] = useState(false)
  const [clave, setClave] = useState(() => crypto.randomUUID())
  const metodoId = metodoElegido || metodos.data?.find((m) => m.es_efectivo)?.id || metodos.data?.[0]?.id || ''
  const caja = useCaja()
  const [desdeCajaElegido, setDesdeCaja] = useState<boolean | null>(null)
  const desdeCaja = usarDesdeCaja(
    desdeCajaElegido,
    !!metodos.data?.find((m) => m.id === metodoId)?.es_efectivo,
    caja.data?.abierta ?? false,
  )

  async function enviar(ev: FormEvent) {
    ev.preventDefault()
    if (!monto || monto <= 0) return setError('Escribe el valor del pago.')
    if (monto > compra.saldo) return setError(`El pago no puede ser mayor que el saldo (${pesos(compra.saldo)}).`)
    setEnviando(true)
    setError(undefined)
    try {
      const c = await api<Compra>(`/compras/${compra.id}/pagos`, {
        method: 'POST',
        idempotencia: clave,
        json: { monto, metodo_pago_id: metodoId, desde_caja: desdeCaja },
      })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['compras'] }),
        cliente.invalidateQueries({ queryKey: ['caja'] }),
      ])
      avisar(c.saldo === 0 ? `Compra pagada por completo.` : `Pago registrado. Queda un saldo de ${pesos(c.saldo)}.`)
      setClave(crypto.randomUUID())
      setMonto(c.saldo)
    } catch (err) {
      setError(mensajeDeError(err))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={enviar} noValidate aria-label="Registrar pago" className="mt-5 flex flex-col gap-3 rounded-tarjeta bg-crema p-4">
      <h3 className="font-serif text-[22px] leading-tight font-medium">Registrar pago</h3>
      <CampoDinero etiqueta="Valor" valor={monto} alCambiar={setMonto} />
      <Selector etiqueta="Pagado con" value={metodoId} onChange={(e) => setMetodo(e.target.value)}>
        {metodos.data?.map((m) => (
          <option key={m.id} value={m.id}>
            {m.nombre}
          </option>
        ))}
      </Selector>
      <SaleDeCaja activo={desdeCaja} alCambiar={setDesdeCaja} />
      {error && <Aviso>{error}</Aviso>}
      <Boton type="submit" disabled={enviando}>
        {enviando ? 'Registrando…' : 'Registrar pago'}
      </Boton>
    </form>
  )
}

function FormAnular({ compra, alTerminar }: { compra: Compra; alTerminar: () => void }) {
  const cliente = useQueryClient()
  const { avisar } = useAvisos()
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState<string>()
  const [enviando, setEnviando] = useState(false)

  async function enviar(ev: FormEvent) {
    ev.preventDefault()
    if (motivo.trim().length < 3) return setError('Cuenta en pocas palabras por qué se anula.')
    setEnviando(true)
    setError(undefined)
    try {
      await api(`/compras/${compra.id}/anular`, { method: 'POST', json: { motivo: motivo.trim() } })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['compras'] }),
        cliente.invalidateQueries({ queryKey: ['inventario'] }),
      ])
      avisar('Compra anulada. Sus lotes salieron del inventario.')
      alTerminar()
    } catch (err) {
      setError(mensajeDeError(err))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
      <p className="text-cafe-medio">
        Se retiran del inventario los {compra.items.length} lotes de esta compra de {pesos(compra.total)}. Solo se puede si
        nada de lo comprado se ha usado todavía.
      </p>
      <AreaTexto etiqueta="Motivo" value={motivo} maxLength={200} onChange={(e) => setMotivo(e.target.value)} />
      {error && <Aviso>{error}</Aviso>}
      <Boton type="submit" variante="peligro" disabled={enviando}>
        {enviando ? 'Anulando…' : 'Anular compra'}
      </Boton>
    </form>
  )
}
