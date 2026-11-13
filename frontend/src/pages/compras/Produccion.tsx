import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useSesion } from '../../auth/contexto'
import { Dialogo } from '../../components/Dialogo'
import { AreaTexto, Aviso, Celda, FilaTabla, ListaDetalle, PanelDetalle, Selector, Tabla, Vacio } from '../../components/formulario'
import { Boton, Campo, Chip, Tarjeta } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api, ErrorApi } from '../../lib/api'
import { cantidad as textoCantidad, dec } from '../../lib/decimal'
import { fechaCorta, hora, pesos } from '../../lib/formato'
import type { Pagina, Produccion as TProduccion, Producto, VistaPreviaProduccion } from '../../lib/tipos'
import { cantidadLegible, costoPorUnidad, fechaDiaMes, fechaIso, hoyIso } from '../../lib/unidades'
import { mensajeDeError } from '../configuracion/acciones'
import { TarjetaLista } from '../configuracion/comun'
import { leerCantidad } from '../inventario/comun'

const TAMANO = 50

/** Registrar producción con vista previa (RF-29) e historial con anulación. */
export function Produccion() {
  const [elegida, setElegida] = useState<string>()
  return (
    <div className="flex flex-col gap-4">
      <NuevaProduccion alRegistrar={(p) => setElegida(p.id)} />
      <Historial elegida={elegida} alElegir={setElegida} />
    </div>
  )
}

function textoError(e: unknown): string {
  if (e instanceof ErrorApi && e.codigo === 'STOCK_INSUFICIENTE') {
    const d = e.detalle as { nombre?: string; requerido?: string; disponible?: string }
    return `No alcanza ${d.nombre?.toLowerCase() ?? 'un insumo'}: se necesitan ${textoCantidad(d.requerido ?? '0')} y hay ${textoCantidad(d.disponible ?? '0')} (sin contar lo vencido).`
  }
  return mensajeDeError(e)
}

function NuevaProduccion({ alRegistrar }: { alRegistrar: (p: TProduccion) => void }) {
  const cliente = useQueryClient()
  const { avisar } = useAvisos()
  const productos = useQuery({ queryKey: ['productos', 'lote'], queryFn: () => api<Producto[]>('/productos?tipo=lote') })
  const [productoId, setProductoId] = useState('')
  const [cantidad, setCantidad] = useState('')
  const [vence, setVence] = useState('')
  const [error, setError] = useState<string>()
  const [enviando, setEnviando] = useState(false)
  const [clave, setClave] = useState(() => crypto.randomUUID())
  const producto = productos.data?.find((p) => p.id === productoId)
  const valor = leerCantidad(cantidad)
  const valido = !!producto && !!valor && dec(valor).gt(0)
  const cuerpo = { producto_id: productoId, cantidad_producida: valor, fecha_vencimiento: vence || null }

  // La vista previa se recalcula sola al cambiar producto, cantidad o vencimiento.
  const previa = useQuery({
    queryKey: ['produccion', 'vista-previa', cuerpo],
    queryFn: () => api<VistaPreviaProduccion>('/producciones/vista-previa', { method: 'POST', json: cuerpo }),
    enabled: valido,
    retry: false,
    staleTime: 0,
  })

  async function enviar(ev: FormEvent) {
    ev.preventDefault()
    if (!valido) return setError('Elige el producto y escribe cuántas unidades salieron.')
    setEnviando(true)
    setError(undefined)
    try {
      const p = await api<TProduccion>('/producciones', { method: 'POST', idempotencia: clave, json: cuerpo })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['producciones'] }),
        cliente.invalidateQueries({ queryKey: ['inventario'] }),
        cliente.invalidateQueries({ queryKey: ['produccion'] }),
      ])
      avisar(`Producción registrada: ${textoCantidad(p.cantidad_producida)} ${p.producto} a ${costoPorUnidad(p.costo_unitario, 'und').replace(' la und', '')} c/u.`)
      setCantidad('')
      setVence('')
      setClave(crypto.randomUUID())
      alRegistrar(p)
    } catch (err) {
      setError(textoError(err))
    } finally {
      setEnviando(false)
    }
  }

  const p = previa.data
  return (
    <Tarjeta className="px-[34px] py-7 max-lg:p-5">
      <form onSubmit={enviar} noValidate className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="flex flex-col gap-4">
          <div>
            <h2 className="font-serif text-[28px] leading-tight font-medium">Registrar producción</h2>
            <p className="mt-1 text-sm text-cafe-suave">Descuenta los insumos de la receta por PEPS y deja las unidades en vitrina.</p>
          </div>
          <Selector etiqueta="Producto" value={productoId} onChange={(e) => setProductoId(e.target.value)}>
            <option value="">Elige un producto por lote</option>
            {productos.data?.map((x) => (
              <option key={x.id} value={x.id} disabled={!x.tiene_receta}>
                {x.nombre}
                {x.tiene_receta ? '' : ' (sin receta)'}
              </option>
            ))}
          </Selector>
          <div className="grid grid-cols-2 gap-3">
            <Campo etiqueta="Unidades producidas" inputMode="decimal" value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
            <Campo
              etiqueta="Vence (opcional)"
              type="date"
              min={hoyIso()}
              value={vence}
              onChange={(e) => setVence(e.target.value)}
            />
          </div>
          {producto?.dias_vida_util != null && !vence && (
            <p className="-mt-2 text-sm text-cafe-suave">
              Sin fecha, vence en {producto.dias_vida_util} {producto.dias_vida_util === 1 ? 'día' : 'días'} (vida útil del producto).
            </p>
          )}
          <p className="text-sm text-cafe-suave">Responsable: quien registra.</p>
        </div>

        <section aria-label="Vista previa" className="flex flex-col rounded-tarjeta border border-linea bg-crema p-5">
          <h3 className="text-[13px] font-semibold tracking-[0.12em] text-dorado-texto uppercase">Antes de confirmar</h3>
          {!valido && <p className="mt-2 text-cafe-medio">Elige el producto y la cantidad para ver qué insumos se van a gastar y cuánto cuesta cada unidad.</p>}
          {valido && previa.isFetching && !p && <p className="mt-2 text-cafe-medio">Calculando…</p>}
          {valido && previa.isError && (
            <div className="mt-3">
              <Aviso>{textoError(previa.error)}</Aviso>
            </div>
          )}
          {valido && p && !previa.isError && (
            <>
              <ul aria-label="Insumos que se consumen" className="mt-2 flex flex-col divide-y divide-linea">
                {p.consumos.map((c) => (
                  <li key={c.insumo_id} className="flex justify-between gap-3 py-2">
                    <span>
                      {c.insumo} <span className="text-cafe-suave">· {cantidadLegible(c.cantidad, c.unidad)}</span>
                    </span>
                    <span>{pesos(c.costo_total)}</span>
                  </li>
                ))}
              </ul>
              <dl className="mt-2 border-t border-dorado-claro pt-2">
                <div className="flex justify-between gap-3 py-1 font-semibold">
                  <dt>Costo total</dt>
                  <dd>{pesos(p.costo_total)}</dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 py-1">
                  <dt className="text-cafe-medio">Cada unidad queda a</dt>
                  <dd className="font-serif text-[32px] leading-none font-semibold [font-variant-numeric:oldstyle-nums]">
                    {costoPorUnidad(p.costo_unitario, 'und').replace(' la und', '')}
                  </dd>
                </div>
                {p.fecha_vencimiento && (
                  <div className="flex justify-between gap-3 py-1 text-sm text-cafe-medio">
                    <dt>Vence</dt>
                    <dd>{fechaIso(p.fecha_vencimiento)}</dd>
                  </div>
                )}
              </dl>
              <p className="mt-1 text-xs text-cafe-suave">Receta versión {p.receta_version}. Costo real de los lotes que se usan primero.</p>
            </>
          )}
          {error && (
            <div className="mt-3">
              <Aviso>{error}</Aviso>
            </div>
          )}
          <Boton type="submit" className="mt-auto w-full max-lg:mt-4 lg:mt-5" disabled={enviando || !p || previa.isError}>
            {enviando ? 'Registrando…' : 'Confirmar producción'}
          </Boton>
        </section>
      </form>
    </Tarjeta>
  )
}

function Historial({ elegida, alElegir }: { elegida?: string; alElegir: (id: string) => void }) {
  const [pagina, setPagina] = useState(1)
  const producciones = useQuery({
    queryKey: ['producciones', pagina],
    queryFn: () => api<Pagina<TProduccion>>(`/producciones?page=${pagina}&size=${TAMANO}`),
    placeholderData: keepPreviousData,
  })
  const lista = producciones.data?.items ?? []
  const actual = lista.find((p) => p.id === elegida) ?? lista[0]
  const paginas = Math.max(1, Math.ceil((producciones.data?.total ?? 0) / TAMANO))
  return (
    <ListaDetalle
      lista={
        <TarjetaLista titulo="Historial de producción">
          {producciones.isError && <Aviso>No pudimos cargar el historial.</Aviso>}
          {producciones.isSuccess && lista.length === 0 && <Vacio>Todavía no se ha registrado ninguna producción.</Vacio>}
          {lista.length > 0 && (
            <Tabla
              columnas={[
                { texto: 'Fecha' },
                { texto: 'Producto' },
                { texto: 'Unidades', derecha: true },
                { texto: 'Costo c/u', derecha: true, ocultarMovil: true },
                { texto: 'Estado', ocultarMovil: true },
              ]}
            >
              {lista.map((p) => {
                const f = new Date(p.fecha)
                return (
                  <FilaTabla key={p.id} seleccionada={p.id === actual?.id} alElegir={() => alElegir(p.id)}>
                    <Celda className="whitespace-nowrap">
                      {fechaCorta(f)}
                      <span className="block text-sm text-cafe-suave">{hora(f)}</span>
                    </Celda>
                    <Celda className="font-semibold">{p.producto}</Celda>
                    <Celda derecha>{textoCantidad(p.cantidad_producida)}</Celda>
                    <Celda derecha ocultarMovil className="whitespace-nowrap">
                      {costoPorUnidad(p.costo_unitario, 'und').replace(' la und', '')}
                    </Celda>
                    <Celda ocultarMovil>{p.anulada ? <Chip>Anulada</Chip> : <Chip tono="exito">Registrada</Chip>}</Celda>
                  </FilaTabla>
                )
              })}
            </Tabla>
          )}
          {paginas > 1 && (
            <nav aria-label="Páginas" className="mt-4 flex items-center justify-between gap-3">
              <Boton variante="secundario" disabled={pagina <= 1} onClick={() => setPagina((x) => x - 1)}>
                Anterior
              </Boton>
              <p className="text-sm text-cafe-medio">
                Página {pagina} de {paginas}
              </p>
              <Boton variante="secundario" disabled={pagina >= paginas} onClick={() => setPagina((x) => x + 1)}>
                Siguiente
              </Boton>
            </nav>
          )}
        </TarjetaLista>
      }
      detalle={actual ? <DetalleProduccion key={actual.id} produccion={actual} /> : null}
    />
  )
}

function DetalleProduccion({ produccion: p }: { produccion: TProduccion }) {
  const { puede } = useSesion()
  const [anulando, setAnulando] = useState(false)
  const f = new Date(p.fecha)
  return (
    <PanelDetalle
      rotulo="Producción"
      titulo={p.producto}
      subtitulo={`${textoCantidad(p.cantidad_producida)} unidades · ${fechaCorta(f)} ${hora(f)}${p.responsable ? ` · ${p.responsable}` : ''}`}
    >
      {p.anulada && <Aviso tono="aviso">Anulada: {p.motivo_anulacion}. Los insumos volvieron a sus lotes.</Aviso>}
      <ul aria-label="Insumos consumidos" className="flex flex-col divide-y divide-linea">
        {p.consumos.map((c) => (
          <li key={c.insumo_id} className="flex justify-between gap-3 py-2">
            <span>
              {c.insumo} <span className="text-cafe-suave">· {cantidadLegible(c.cantidad, c.unidad)}</span>
            </span>
            <span>{pesos(c.costo_total)}</span>
          </li>
        ))}
      </ul>
      <dl className="mt-2 border-t border-dorado-claro pt-2">
        <div className="flex justify-between gap-3 py-1 font-semibold">
          <dt>Costo total</dt>
          <dd>{pesos(p.costo_total)}</dd>
        </div>
        <div className="flex justify-between gap-3 py-1">
          <dt className="text-cafe-medio">Costo por unidad</dt>
          <dd>{costoPorUnidad(p.costo_unitario, 'und').replace(' la und', '')}</dd>
        </div>
        {p.fecha_vencimiento && (
          <div className="flex justify-between gap-3 py-1">
            <dt className="text-cafe-medio">Vence</dt>
            <dd>{fechaDiaMes(p.fecha_vencimiento, hoyIso())}</dd>
          </div>
        )}
        <div className="flex justify-between gap-3 py-1 text-sm text-cafe-suave">
          <dt>Receta</dt>
          <dd>Versión {p.receta_version}</dd>
        </div>
      </dl>
      {!p.anulada && puede('produccion.anular') && (
        <Boton variante="peligro" className="mt-5 w-full" onClick={() => setAnulando(true)}>
          Anular producción
        </Boton>
      )}
      <Dialogo abierto={anulando} alCerrar={() => setAnulando(false)} titulo="Anular producción">
        {anulando && <FormAnular produccion={p} alTerminar={() => setAnulando(false)} />}
      </Dialogo>
    </PanelDetalle>
  )
}

function FormAnular({ produccion, alTerminar }: { produccion: TProduccion; alTerminar: () => void }) {
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
      await api(`/producciones/${produccion.id}/anular`, { method: 'POST', json: { motivo: motivo.trim() } })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['producciones'] }),
        cliente.invalidateQueries({ queryKey: ['inventario'] }),
      ])
      avisar('Producción anulada. Los insumos volvieron a sus lotes.')
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
        Los insumos vuelven a sus mismos lotes y salen las {textoCantidad(produccion.cantidad_producida)} unidades de vitrina.
        Solo se puede si ninguna se ha vendido.
      </p>
      <AreaTexto etiqueta="Motivo" value={motivo} maxLength={200} onChange={(e) => setMotivo(e.target.value)} />
      {error && <Aviso>{error}</Aviso>}
      <Boton type="submit" variante="peligro" disabled={enviando}>
        {enviando ? 'Anulando…' : 'Anular producción'}
      </Boton>
    </form>
  )
}
