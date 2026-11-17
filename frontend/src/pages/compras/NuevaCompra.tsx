import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Plus, Trash2 } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { Buscador } from '../../components/Buscador'
import { CampoDinero } from '../../components/CampoDinero'
import { Aviso, Selector } from '../../components/formulario'
import { Boton, Campo, Tarjeta } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api } from '../../lib/api'
import { unir } from '../../lib/clases'
import { dec } from '../../lib/decimal'
import { pesos } from '../../lib/formato'
import type { Compra, Insumo, MetodoPago, Proveedor } from '../../lib/tipos'
import { cantidadLegible, costoPorUnidad, hoyIso } from '../../lib/unidades'
import { mensajeDeError } from '../configuracion/acciones'
import { leerCantidad } from '../inventario/comun'
import { SaleDeCaja } from '../caja/SaleDeCaja'
import { useCaja, usarDesdeCaja } from '../caja/usarCaja'

interface Linea {
  clave: number
  insumo_id: string
  presentacion_id: string
  cantidad: string
  costo: number | null
  vence: string
}

const lineaVacia = (clave: number): Linea => ({ clave, insumo_id: '', presentacion_id: '', cantidad: '', costo: null, vence: '' })

/** Registrar compra: cada línea crea un lote del insumo en su unidad base (RF-24). */
export function NuevaCompra({ alRegistrar }: { alRegistrar: (c: Compra) => void }) {
  const { avisar } = useAvisos()
  const cliente = useQueryClient()
  const insumos = useQuery({ queryKey: ['insumos'], queryFn: () => api<Insumo[]>('/insumos') })
  const proveedores = useQuery({ queryKey: ['proveedores'], queryFn: () => api<Proveedor[]>('/proveedores') })
  const metodos = useQuery({ queryKey: ['metodos-pago'], queryFn: () => api<MetodoPago[]>('/metodos-pago') })
  const [proveedorId, setProveedorId] = useState('')
  const [fecha, setFecha] = useState(hoyIso())
  const [factura, setFactura] = useState('')
  const [estado, setEstado] = useState<'por_pagar' | 'contado'>('por_pagar')
  const [limitePago, setLimitePago] = useState('')
  const [metodoElegido, setMetodo] = useState('')
  const [lineas, setLineas] = useState<Linea[]>([lineaVacia(0)])
  const [soporte, setSoporte] = useState<string | null>(null)
  const [subiendo, setSubiendo] = useState(false)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [error, setError] = useState<string>()
  const [enviando, setEnviando] = useState(false)
  const [clave, setClave] = useState(() => crypto.randomUUID())
  const archivo = useRef<HTMLInputElement>(null)
  const metodoId = metodoElegido || metodos.data?.find((m) => m.es_efectivo)?.id || metodos.data?.[0]?.id || ''
  const caja = useCaja()
  const [desdeCajaElegido, setDesdeCaja] = useState<boolean | null>(null)
  const desdeCaja = usarDesdeCaja(
    desdeCajaElegido,
    !!metodos.data?.find((m) => m.id === metodoId)?.es_efectivo,
    caja.data?.abierta ?? false,
  )

  const porId = new Map((insumos.data ?? []).map((i) => [i.id, i]))
  const proveedor = proveedores.data?.find((p) => p.id === proveedorId)
  // Primero los insumos que suministra el proveedor elegido.
  const delProveedor = new Set(proveedor?.insumos.map((i) => i.id))
  const ordenados = [...(insumos.data ?? [])].sort((a, b) => Number(delProveedor.has(b.id)) - Number(delProveedor.has(a.id)))
  const total = lineas.reduce((s, l) => s + (l.costo ?? 0), 0)
  const opcionesInsumos = ordenados.map((i) => ({
    valor: i.id,
    texto: i.nombre,
    detalle: delProveedor.has(i.id) ? `${i.unidad_base} · lo trae ${proveedor?.nombre}` : i.unidad_base,
  }))

  function cambiar(clave: number, cambio: Partial<Linea>) {
    setLineas((ls) => ls.map((l) => (l.clave === clave ? { ...l, ...cambio } : l)))
  }

  /** "= 50 kg a $3.000 el kg" debajo de la línea, para revisar antes de guardar. */
  function resumenLinea(l: Linea): string | null {
    const insumo = porId.get(l.insumo_id)
    const c = leerCantidad(l.cantidad)
    if (!insumo || !c || dec(c).lte(0)) return null
    const factor = insumo.presentaciones.find((p) => p.id === l.presentacion_id)?.factor ?? '1'
    const base = dec(c).mul(dec(factor))
    const texto = `= ${cantidadLegible(base.toFixed(), insumo.unidad_base)}`
    if (!l.costo) return texto
    return `${texto} a ${costoPorUnidad(dec(String(l.costo)).div(base).toFixed(), insumo.unidad_base)}`
  }

  async function subir(f: File) {
    setSubiendo(true)
    try {
      const datos = new FormData()
      datos.append('archivo', f)
      setSoporte((await api<{ url: string }>('/archivos', { method: 'POST', body: datos })).url)
    } catch {
      setErrores((e) => ({ ...e, soporte: 'No pudimos subir la foto. Prueba con una imagen de menos de 5 MB.' }))
    } finally {
      setSubiendo(false)
    }
  }

  async function enviar(ev: FormEvent) {
    ev.preventDefault()
    const e: Record<string, string> = {}
    const usadas = lineas.filter((l) => l.insumo_id || l.cantidad || l.costo !== null)
    for (const l of usadas) {
      if (!l.insumo_id) e[`i${l.clave}`] = 'Elige el insumo.'
      const c = leerCantidad(l.cantidad)
      if (!c || dec(c).lte(0)) e[`c${l.clave}`] = 'Escribe la cantidad.'
      if (l.costo === null) e[`p${l.clave}`] = 'Escribe lo que costó.'
    }
    if (usadas.length === 0) e.lineas = 'Agrega al menos un insumo.'
    if (estado === 'contado' && !metodoId) e.metodo = 'Elige con qué se pagó.'
    setErrores(e)
    if (Object.keys(e).length) return
    setEnviando(true)
    setError(undefined)
    try {
      const compra = await api<Compra>('/compras', {
        method: 'POST',
        idempotencia: clave,
        json: {
          proveedor_id: proveedorId || null,
          fecha,
          numero_factura_proveedor: factura.trim() || null,
          soporte_url: soporte,
          estado_pago: estado,
          metodo_pago_id: estado === 'contado' ? metodoId : null,
          desde_caja: estado === 'contado' && desdeCaja,
          fecha_limite_pago: estado === 'por_pagar' && limitePago ? limitePago : null,
          items: usadas.map((l) => ({
            insumo_id: l.insumo_id,
            presentacion_id: l.presentacion_id || null,
            cantidad: leerCantidad(l.cantidad),
            costo_total: l.costo,
            fecha_vencimiento: l.vence || null,
          })),
        },
      })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['compras'] }),
        cliente.invalidateQueries({ queryKey: ['inventario'] }),
      ])
      avisar(`Compra registrada por ${pesos(compra.total)}: ${compra.items.length} ${compra.items.length === 1 ? 'lote nuevo' : 'lotes nuevos'} en inventario.`)
      setLineas([lineaVacia(0)])
      setSoporte(null)
      setFactura('')
      setClave(crypto.randomUUID())
      alRegistrar(compra)
    } catch (err) {
      setError(mensajeDeError(err))
    } finally {
      setEnviando(false)
    }
  }

  const campo = (err?: string) =>
    unir(
      'h-12 w-full rounded-control border bg-blanco px-3 text-base focus:border-dorado-borde focus:outline-none',
      err ? 'border-peligro' : 'border-dorado-claro',
    )

  return (
    <Tarjeta className="px-[34px] py-7 max-lg:p-5">
      <form onSubmit={enviar} noValidate>
        <h2 className="font-serif text-[28px] leading-tight font-medium">Registrar compra</h2>
        <p className="mt-1 text-sm text-cafe-suave">Cada línea crea un lote con su costo real; el inventario se actualiza al guardar.</p>

        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <Buscador
            etiqueta="Proveedor"
            placeholder="Busca o deja sin proveedor"
            opciones={[{ valor: '', texto: 'Sin proveedor' }, ...(proveedores.data ?? []).map((p) => ({ valor: p.id, texto: p.nombre }))]}
            valor={proveedorId}
            alCambiar={setProveedorId}
          />
          <Campo etiqueta="Fecha" type="date" value={fecha} max={hoyIso()} onChange={(e) => {
              setFecha(e.target.value)
              // La fecha límite no puede quedar antes de la compra: si pasa, se borra.
              if (limitePago && limitePago < e.target.value) setLimitePago('')
            }} />
          <Campo etiqueta="N.º de factura (opcional)" value={factura} maxLength={60} onChange={(e) => setFactura(e.target.value)} />
        </div>

        <fieldset className="mt-6">
          <legend className="mb-2 text-sm font-semibold">Insumos</legend>
          <div aria-hidden className="mb-1.5 hidden gap-2.5 px-[15px] text-[13px] font-semibold tracking-[0.08em] text-cafe-suave uppercase md:grid md:grid-cols-[minmax(0,2fr)_minmax(0,1.6fr)_6rem_9rem_9.5rem_auto]">
            <span>Insumo</span>
            <span>Presentación</span>
            <span className="text-right">Cantidad</span>
            <span>Costo total</span>
            <span>Vence</span>
            <span className="w-12" />
          </div>
          <ol className="flex flex-col gap-3">
            {lineas.map((l, n) => {
              const insumo = porId.get(l.insumo_id)
              const resumen = resumenLinea(l)
              return (
                <li key={l.clave} aria-label={`Línea ${n + 1}`} className="rounded-tarjeta border border-linea p-3.5">
                  <div className="grid grid-cols-2 gap-2.5 md:grid-cols-[minmax(0,2fr)_minmax(0,1.6fr)_6rem_9rem_9.5rem_auto] md:items-start">
                    <div className="col-span-2 md:col-span-1">
                      <span aria-hidden className="mb-1 block text-xs font-semibold text-cafe-suave md:hidden">Insumo</span>
                      <Buscador
                        etiqueta="Insumo"
                        ocultarEtiqueta
                        placeholder="Busca un insumo"
                        opciones={opcionesInsumos}
                        valor={l.insumo_id}
                        alCambiar={(v) =>
                          cambiar(l.clave, { insumo_id: v, presentacion_id: porId.get(v)?.presentaciones.find((p) => p.activa)?.id ?? '' })
                        }
                        error={errores[`i${l.clave}`]}
                      />
                    </div>
                    <div className="col-span-2 md:col-span-1">
                      <span aria-hidden className="mb-1 block text-xs font-semibold text-cafe-suave md:hidden">Presentación</span>
                      <select
                        aria-label="Presentación"
                        value={l.presentacion_id}
                        disabled={!insumo}
                        onChange={(e) => cambiar(l.clave, { presentacion_id: e.target.value })}
                        className={campo()}
                      >
                        <option value="">{insumo ? `En ${insumo.unidad_base}` : 'Presentación'}</option>
                        {insumo?.presentaciones
                          .filter((p) => p.activa)
                          .map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.nombre}
                            </option>
                          ))}
                      </select>
                    </div>
                    <div>
                      <span aria-hidden className="mb-1 block text-xs font-semibold text-cafe-suave md:hidden">Cantidad</span>
                      <input
                        aria-label="Cantidad"
                        inputMode="decimal"
                        value={l.cantidad}
                        onChange={(e) => cambiar(l.clave, { cantidad: e.target.value })}
                        className={unir(campo(errores[`c${l.clave}`]), 'text-right')}
                      />
                      {errores[`c${l.clave}`] && <p className="mt-1 text-sm text-peligro-texto">{errores[`c${l.clave}`]}</p>}
                    </div>
                    <div>
                      <span aria-hidden className="mb-1 block text-xs font-semibold text-cafe-suave md:hidden">Costo total</span>
                      <CampoDinero
                        etiqueta="Costo total"
                        ocultarEtiqueta
                        valor={l.costo}
                        alCambiar={(v) => cambiar(l.clave, { costo: v })}
                        error={errores[`p${l.clave}`]}
                      />
                    </div>
                    <div>
                      <span aria-hidden className="mb-1 block text-xs font-semibold text-cafe-suave md:hidden">Vence</span>
                      <input
                        aria-label="Vence"
                        type="date"
                        value={l.vence}
                        min={fecha}
                        onChange={(e) => cambiar(l.clave, { vence: e.target.value })}
                        className={campo()}
                      />
                    </div>
                    <button
                      type="button"
                      aria-label={`Quitar línea ${n + 1}`}
                      title="Quitar línea"
                      disabled={lineas.length === 1}
                      onClick={() => setLineas((ls) => ls.filter((x) => x.clave !== l.clave))}
                      className="grid size-12 place-items-center self-end justify-self-end rounded-control text-cafe-suave hover:bg-peligro-fondo hover:text-peligro-texto disabled:opacity-30"
                    >
                      <Trash2 aria-hidden className="size-[18px]" />
                    </button>
                  </div>
                  {resumen && <p className="mt-2 text-sm text-cafe-medio">{resumen}</p>}
                </li>
              )
            })}
          </ol>
          {errores.lineas && <p className="mt-2 text-sm text-peligro-texto">{errores.lineas}</p>}
          <button
            type="button"
            onClick={() => setLineas((ls) => [...ls, lineaVacia(Math.max(...ls.map((l) => l.clave)) + 1)])}
            className="mt-2.5 inline-flex h-10 items-center gap-1.5 rounded-control px-3 font-semibold text-fucsia hover:bg-rosa-suave"
          >
            <Plus aria-hidden className="size-[18px]" strokeWidth={2.2} />
            Agregar línea
          </button>
        </fieldset>

        <div className="mt-6 grid gap-5 border-t border-linea pt-5 md:grid-cols-2">
          <div className="flex flex-col gap-4">
            <fieldset>
              <legend className="mb-1.5 text-sm font-semibold">Pago</legend>
              <div className="flex gap-5">
                {(
                  [
                    ['por_pagar', 'Por pagar'],
                    ['contado', 'De contado'],
                  ] as const
                ).map(([v, t]) => (
                  <label key={v} className="flex cursor-pointer items-center gap-2">
                    <input type="radio" name="estado_pago" checked={estado === v} onChange={() => setEstado(v)} className="size-[18px] accent-fucsia" />
                    {t}
                  </label>
                ))}
              </div>
            </fieldset>
            {estado === 'contado' && (
              <Selector etiqueta="Pagado con" value={metodoId} onChange={(e) => setMetodo(e.target.value)}>
                {metodos.data?.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.nombre}
                  </option>
                ))}
              </Selector>
            )}
            {estado === 'por_pagar' && (
              <Campo
                etiqueta="Pagar antes del (opcional)"
                type="date"
                value={limitePago}
                min={fecha}
                onChange={(e) => setLimitePago(e.target.value)}
              />
            )}
            {estado === 'contado' && <SaleDeCaja activo={desdeCaja} alCambiar={setDesdeCaja} />}
            <div>
              <p className="mb-1.5 text-sm font-semibold">Soporte (foto de la factura)</p>
              <input
                ref={archivo}
                type="file"
                accept="image/*"
                capture="environment"
                className="sr-only"
                tabIndex={-1}
                aria-hidden
                onChange={(e) => e.target.files?.[0] && subir(e.target.files[0])}
              />
              <Boton variante="secundario" className="h-11 px-4 text-[15px]" disabled={subiendo} onClick={() => archivo.current?.click()}>
                <Camera aria-hidden className="size-[18px]" />
                {subiendo ? 'Subiendo…' : soporte ? 'Cambiar foto' : 'Tomar o subir foto'}
              </Boton>
              {soporte && <p className="mt-1.5 text-sm text-exito-texto">Foto adjunta.</p>}
              {errores.soporte && <p className="mt-1.5 text-sm text-peligro-texto">{errores.soporte}</p>}
            </div>
          </div>
          <div className="flex flex-col justify-end gap-3">
            <p className="flex items-baseline justify-between gap-3">
              <span className="text-cafe-medio">Total de la compra</span>
              <span className="font-serif text-[40px] leading-none font-semibold [font-variant-numeric:oldstyle-nums]">{pesos(total)}</span>
            </p>
            {error && <Aviso>{error}</Aviso>}
            <Boton type="submit" disabled={enviando}>
              {enviando ? 'Registrando…' : 'Registrar compra'}
            </Boton>
          </div>
        </div>
      </form>
    </Tarjeta>
  )
}
