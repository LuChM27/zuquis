import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ban, MessageCircle, Printer } from 'lucide-react'
import { useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { useSesion } from '../../auth/contexto'
import { Dialogo } from '../../components/Dialogo'
import { Aviso, Celda, FilaTabla, ListaDetalle, PanelDetalle, Tabla, Vacio } from '../../components/formulario'
import { Boton, Campo, Chip, EncabezadoPagina, Tarjeta, TituloTarjeta } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api } from '../../lib/api'
import { unir } from '../../lib/clases'
import { cantidad } from '../../lib/decimal'
import { fechaConDia, hora, pesos } from '../../lib/formato'
import type { Pagina, ResumenVentas, Venta } from '../../lib/tipos'
import { hoyIso } from '../../lib/unidades'
import { Cifra } from '../inventario/Indicadores'
import { useComprobante } from '../vender/comprobante'

const TAMANO = 25
const SERVICIO: Record<string, string> = { local: 'En local', llevar: 'Para llevar', domicilio: 'Domicilio' }
const numeroVenta = (n: number) => `n.º ${String(n).padStart(4, '0')}`
/** Mediodía del día elegido: así la fecha no se corre por la zona horaria. */
const fechaDelDia = (iso: string) => new Date(`${iso}T12:00:00-05:00`)

/** Ventas de un día: resumen (qué se vendió y cómo se cobró), lista y detalle de cada venta. */
export function Ventas() {
  const [params, setParams] = useSearchParams()
  const dia = params.get('dia') ?? hoyIso()
  const elegida = params.get('venta') ?? undefined
  const [numero, setNumero] = useState('')
  const fijar = (cambios: Record<string, string | null>) => {
    const siguiente = new URLSearchParams(params)
    for (const [k, v] of Object.entries(cambios)) {
      if (v) siguiente.set(k, v)
      else siguiente.delete(k)
    }
    setParams(siguiente)
  }

  return (
    <>
      <EncabezadoPagina
        contexto={dia === hoyIso() ? `Hoy, ${fechaConDia(fechaDelDia(dia)).toLowerCase()}` : fechaConDia(fechaDelDia(dia))}
        titulo="Ventas"
        acciones={
          <>
            <Campo
              etiqueta="Día"
              type="date"
              value={dia}
              max={hoyIso()}
              onChange={(e) => e.target.value && fijar({ dia: e.target.value, venta: null })}
              className="w-[180px]"
            />
            <Campo
              etiqueta="Buscar por número"
              inputMode="numeric"
              placeholder="142"
              value={numero}
              onChange={(e) => setNumero(e.target.value.replace(/\D/g, ''))}
              className="w-[180px]"
            />
          </>
        }
      />
      {numero ? (
        <BusquedaPorNumero numero={Number(numero)} elegida={elegida} alElegir={(id) => fijar({ venta: id })} />
      ) : (
        <>
          <Resumen dia={dia} />
          <ListaVentas dia={dia} elegida={elegida} alElegir={(id) => fijar({ venta: id })} />
        </>
      )}
    </>
  )
}

function Resumen({ dia }: { dia: string }) {
  const resumen = useQuery({
    queryKey: ['ventas', 'resumen', dia],
    queryFn: () => api<ResumenVentas>(`/ventas/resumen?desde=${dia}&hasta=${dia}`),
  })
  const r = resumen.data
  return (
    <>
      <div className="mb-4 grid grid-cols-2 gap-2.5 sm:gap-4 xl:grid-cols-4">
        <Cifra titulo="Vendido" valor={r ? pesos(r.total) : '—'} detalle="Total de las ventas, sin propinas" />
        <Cifra
          titulo="Ventas"
          valor={r ? String(r.ventas) : '—'}
          detalle={r?.anuladas ? `${r.anuladas} ${r.anuladas === 1 ? 'anulada' : 'anuladas'} aparte` : 'Ninguna anulada'}
        />
        <Cifra titulo="Propinas" valor={r ? pesos(r.propinas) : '—'} detalle="Dinero de terceros, no es venta" />
        <Cifra titulo="Descuentos y regalos" valor={r ? pesos(r.descuentos) : '—'} detalle="Lo que se dejó de cobrar" />
      </div>
      <div className="mb-4 grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Tarjeta>
          <TituloTarjeta>Lo que se vendió</TituloTarjeta>
          {r && r.productos.length === 0 ? (
            <Vacio>No hay ventas este día.</Vacio>
          ) : (
            <div className="mt-3 max-h-[340px] overflow-y-auto">
              <Tabla columnas={[{ texto: 'Producto' }, { texto: 'Cantidad', derecha: true }, { texto: 'Valor', derecha: true }]}>
                {r?.productos.map((p) => (
                  <tr key={p.producto_id} className="border-b border-linea last:border-b-0">
                    <Celda className="font-medium">{p.producto}</Celda>
                    <Celda derecha>{cantidad(p.cantidad)}</Celda>
                    <Celda derecha className="font-semibold">
                      {pesos(p.valor)}
                    </Celda>
                  </tr>
                ))}
              </Tabla>
            </div>
          )}
        </Tarjeta>
        <Tarjeta>
          <TituloTarjeta>Cobrado por método</TituloTarjeta>
          <dl className="mt-3 grid gap-2.5">
            {r?.por_metodo.map((m) => (
              <div key={m.metodo_pago_id} className="flex items-baseline justify-between gap-3">
                <dt>{m.metodo}</dt>
                <dd className="font-semibold">{pesos(m.monto)}</dd>
              </div>
            ))}
            {r && r.por_metodo.length === 0 && <p className="text-cafe-medio">Nada cobrado.</p>}
          </dl>
          {r && r.por_metodo.length > 0 && (
            <p className="mt-3 text-sm text-cafe-suave">Incluye propinas y domicilios cobrados con cada método.</p>
          )}
        </Tarjeta>
      </div>
    </>
  )
}

function ListaVentas({ dia, elegida, alElegir }: { dia: string; elegida?: string; alElegir: (id: string) => void }) {
  const [pagina, setPagina] = useState(1)
  const ventas = useQuery({
    queryKey: ['ventas', 'lista', dia, pagina],
    queryFn: () => api<Pagina<Venta>>(`/ventas?desde=${dia}&hasta=${dia}&page=${pagina}&size=${TAMANO}`),
  })
  const paginas = Math.max(1, Math.ceil((ventas.data?.total ?? 0) / TAMANO))
  return (
    <TablaVentas
      ventas={ventas.data?.items}
      cargando={ventas.isPending}
      vacio="No hay ventas este día."
      elegida={elegida}
      alElegir={alElegir}
      paginacion={
        paginas > 1 && (
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
        )
      }
    />
  )
}

function BusquedaPorNumero({ numero, elegida, alElegir }: { numero: number; elegida?: string; alElegir: (id: string) => void }) {
  const ventas = useQuery({
    queryKey: ['ventas', 'numero', numero],
    queryFn: () => api<Pagina<Venta>>(`/ventas?numero=${numero}`),
    enabled: numero > 0,
  })
  return (
    <TablaVentas
      ventas={ventas.data?.items}
      cargando={ventas.isPending}
      vacio={`No hay ninguna venta ${numeroVenta(numero)}.`}
      elegida={elegida ?? ventas.data?.items[0]?.id}
      alElegir={alElegir}
    />
  )
}

/** "2 × Capuchino, 1 × Pastel de pollo" */
function queSeVendio(v: Venta): string {
  return v.items.map((i) => `${cantidad(i.cantidad)} × ${i.producto}`).join(', ')
}

function TablaVentas({
  ventas,
  cargando,
  vacio,
  elegida,
  alElegir,
  paginacion,
}: {
  ventas?: Venta[]
  cargando: boolean
  vacio: string
  elegida?: string
  alElegir: (id: string) => void
  paginacion?: React.ReactNode
}) {
  const actual = ventas?.find((v) => v.id === elegida)
  return (
    <ListaDetalle
      lista={
        <Tarjeta>
          {cargando ? (
            <p className="text-cafe-medio">Cargando…</p>
          ) : !ventas?.length ? (
            <Vacio>{vacio}</Vacio>
          ) : (
            <Tabla
              columnas={[
                { texto: 'Venta' },
                { texto: 'Qué se vendió' },
                { texto: 'Cajero', ocultarMovil: true },
                { texto: 'Total', derecha: true },
              ]}
            >
              {ventas.map((v) => (
                <FilaTabla key={v.id} seleccionada={v.id === elegida} alElegir={() => alElegir(v.id)}>
                  <Celda className="whitespace-nowrap">
                    <span className="block font-semibold">{numeroVenta(v.numero)}</span>
                    <span className="block text-sm text-cafe-suave">{hora(new Date(v.fecha))}</span>
                  </Celda>
                  <Celda>
                    <span className="line-clamp-2 text-[15px]">{queSeVendio(v)}</span>
                  </Celda>
                  <Celda ocultarMovil className="text-cafe-medio">
                    {v.cajero}
                  </Celda>
                  <Celda derecha>
                    {v.estado === 'anulada' ? (
                      <Chip tono="peligro">Anulada</Chip>
                    ) : (
                      <span className="font-semibold whitespace-nowrap">{pesos(v.total)}</span>
                    )}
                  </Celda>
                </FilaTabla>
              ))}
            </Tabla>
          )}
          {paginacion}
        </Tarjeta>
      }
      detalle={actual ? <DetalleVenta key={actual.id} venta={actual} /> : null}
    />
  )
}

/** La venta como un comprobante: qué se vendió, descuentos, totales y cómo se pagó. */
function DetalleVenta({ venta }: { venta: Venta }) {
  const { puede } = useSesion()
  const { imprimir, compartir, ocupado } = useComprobante(venta)
  const [anulando, setAnulando] = useState(false)
  const fecha = new Date(venta.fecha)
  const anulada = venta.estado === 'anulada'
  const fila = 'flex items-baseline justify-between gap-3'

  return (
    <PanelDetalle
      rotulo={anulada ? 'Venta anulada' : 'Venta'}
      titulo={`Venta ${numeroVenta(venta.numero)}`}
      subtitulo={`${fechaConDia(fecha)} · ${hora(fecha)} · ${SERVICIO[venta.tipo_servicio] ?? venta.tipo_servicio}${venta.cajero ? ` · ${venta.cajero}` : ''}`}
    >
      {anulada && (
        <div className="mb-4">
          <Aviso>
            Anulada{venta.anulada_en ? ` a las ${hora(new Date(venta.anulada_en))}` : ''}: {venta.motivo_anulacion}
          </Aviso>
        </div>
      )}
      <ul aria-label="Productos" className="border-b border-dorado-claro pb-2">
        {venta.items.map((i) => {
          const regalo = i.descuento > 0 && i.descuento === i.bruto
          return (
            <li key={i.id} className="border-b border-linea py-2.5 last:border-b-0">
              <div className={fila}>
                <span className="font-medium">
                  {cantidad(i.cantidad)} × {i.producto}
                </span>
                <span className="font-semibold">{pesos(i.subtotal)}</span>
              </div>
              <p className="text-sm text-cafe-suave">{pesos(i.precio_unitario)} c/u</p>
              {i.modificadores.map((m) => (
                <p key={m.modificador_id} className="text-sm text-cafe-suave">
                  + {m.nombre} ({pesos(m.precio)})
                </p>
              ))}
              {i.nota && <p className="text-sm text-cafe-suave">{i.nota}</p>}
              {regalo ? (
                <p className="text-sm font-semibold text-fucsia">Regalo</p>
              ) : (
                i.descuento > 0 && <p className="text-sm text-peligro-texto">Descuento −{pesos(i.descuento)}</p>
              )}
            </li>
          )
        })}
      </ul>
      <dl className="mt-3 grid gap-1.5 text-[15px]">
        <div className={fila}>
          <dt className="text-cafe-medio">Subtotal</dt>
          <dd>{pesos(venta.subtotal)}</dd>
        </div>
        {venta.descuento_total > 0 && (
          <div className={fila}>
            <dt className="text-cafe-medio">
              {venta.cortesia ? 'Cortesía' : 'Descuentos'}
              {venta.descuento_motivo ? ` · ${venta.descuento_motivo}` : ''}
            </dt>
            <dd className="text-fucsia">−{pesos(venta.descuento_total)}</dd>
          </div>
        )}
        <div className={unir(fila, 'text-[17px] font-bold')}>
          <dt>Total de la venta</dt>
          <dd>{pesos(venta.total)}</dd>
        </div>
        {venta.propina > 0 && (
          <div className={fila}>
            <dt className="text-cafe-medio">Propina</dt>
            <dd>{pesos(venta.propina)}</dd>
          </div>
        )}
        {venta.valor_domicilio > 0 && (
          <div className={fila}>
            <dt className="text-cafe-medio">Domicilio</dt>
            <dd>{pesos(venta.valor_domicilio)}</dd>
          </div>
        )}
      </dl>
      {venta.pagos.length > 0 && (
        <>
          <h3 className="mt-4 text-[13px] font-semibold tracking-[0.08em] text-cafe-suave uppercase">Cómo pagó</h3>
          <dl className="mt-1.5 grid gap-1.5 text-[15px]">
            {venta.pagos.map((p) => (
              <div key={p.metodo_pago_id}>
                <div className={fila}>
                  <dt>{p.metodo}</dt>
                  <dd className="font-semibold">{pesos(p.monto)}</dd>
                </div>
                {p.recibido !== null && p.cambio > 0 && (
                  <p className="text-sm text-cafe-suave">
                    Recibió {pesos(p.recibido)} · cambio {pesos(p.cambio)}
                  </p>
                )}
              </div>
            ))}
          </dl>
        </>
      )}
      {puede('reportes.ver') && (
        <p className="mt-4 rounded-control bg-crema p-3 text-sm text-cafe-medio">
          Costo de lo vendido {pesos(venta.costo_total)} · ganancia bruta {pesos(venta.total - venta.costo_total)}
        </p>
      )}
      <div className="mt-5 grid grid-cols-2 gap-3">
        <Boton variante="secundario" onClick={() => void imprimir()} disabled={ocupado}>
          <Printer aria-hidden className="size-5" strokeWidth={1.7} />
          Imprimir
        </Boton>
        <Boton variante="secundario" onClick={() => void compartir()} disabled={ocupado}>
          <MessageCircle aria-hidden className="size-5" strokeWidth={1.7} />
          Compartir
        </Boton>
        {!anulada && puede('ventas.anular') && (
          <Boton variante="peligro" className="col-span-2" onClick={() => setAnulando(true)}>
            <Ban aria-hidden className="size-5" strokeWidth={1.7} />
            Anular venta
          </Boton>
        )}
      </div>
      <DialogoAnular venta={venta} abierto={anulando} alCerrar={() => setAnulando(false)} />
    </PanelDetalle>
  )
}

function DialogoAnular({ venta, abierto, alCerrar }: { venta: Venta; abierto: boolean; alCerrar: () => void }) {
  return (
    <Dialogo abierto={abierto} alCerrar={alCerrar} titulo={`Anular la venta ${numeroVenta(venta.numero)}`} rotulo="Anulación">
      {abierto && <FormAnular venta={venta} alCerrar={alCerrar} />}
    </Dialogo>
  )
}

function FormAnular({ venta, alCerrar }: { venta: Venta; alCerrar: () => void }) {
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const [motivo, setMotivo] = useState('')
  const [intento, setIntento] = useState(false)
  const clave = useRef(crypto.randomUUID())
  const anular = useMutation({
    mutationFn: () =>
      api<Venta>(`/ventas/${venta.id}/anular`, { method: 'POST', idempotencia: clave.current, json: { motivo: motivo.trim() } }),
    onSuccess: () => {
      avisar(`Venta ${numeroVenta(venta.numero)} anulada.`)
      for (const clave of [['ventas'], ['caja'], ['productos'], ['inventario']]) void clienteQuery.invalidateQueries({ queryKey: clave })
      alCerrar()
    },
    onError: (e) => avisar(e.message, 'error'),
  })
  const corto = motivo.trim().length < 3
  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        setIntento(true)
        if (!corto) anular.mutate()
      }}
    >
      <p className="text-cafe-medio">
        Los productos vuelven al inventario, a los mismos lotes. Los {pesos(venta.cobrado)} cobrados salen de la caja abierta de hoy, por el
        mismo método con que se pagaron.
      </p>
      <Campo
        etiqueta="Motivo"
        placeholder="Se cobró dos veces, el cliente devolvió el pedido…"
        value={motivo}
        maxLength={200}
        onChange={(e) => setMotivo(e.target.value)}
        error={intento && corto ? 'Cuenta en pocas palabras por qué se anula.' : undefined}
        autoFocus
      />
      <div className="flex justify-end gap-3">
        <Boton variante="secundario" onClick={alCerrar}>
          Volver
        </Boton>
        <Boton type="submit" variante="peligro" disabled={anular.isPending}>
          {anular.isPending ? 'Anulando…' : 'Anular venta'}
        </Boton>
      </div>
    </form>
  )
}
