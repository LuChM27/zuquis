import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Aviso } from '../../components/formulario'
import { Boton, Campo } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api, ErrorApi } from '../../lib/api'
import { unir } from '../../lib/clases'
import { cantidad as textoCantidad, dec } from '../../lib/decimal'
import { fechaCorta, pesos } from '../../lib/formato'
import type { CostoReceta, Insumo, Receta } from '../../lib/tipos'
import { cantidadLegible } from '../../lib/unidades'
import { mensajeDeError } from '../configuracion/acciones'
import { leerCantidad } from '../inventario/comun'

/** Margen sobre el precio por debajo del cual se avisa (RF-07). */
export const MARGEN_MINIMO = 30

interface Fila {
  clave: number
  insumo_id: string
  cantidad: string
}

/** Lee la receta vigente; un 404 significa que todavía no tiene. */
async function leerReceta(base: string): Promise<Receta | null> {
  try {
    return await api<Receta>(`${base}/receta`)
  } catch (e) {
    if (e instanceof ErrorApi && e.estado === 404) return null
    throw e
  }
}

/**
 * Receta de un producto o una adición (`base` = /productos/{id} o /modificadores/{id}):
 * editor de ítems y rendimiento, costo teórico con margen y versiones anteriores. Guardar crea
 * una versión nueva; lo ya producido conserva la receta con la que se hizo.
 */
export function EditorReceta({ base, editable }: { base: string; editable: boolean }) {
  const receta = useQuery({ queryKey: ['receta', base], queryFn: () => leerReceta(base) })
  if (receta.isPending) return <p className="text-cafe-medio">Cargando la receta…</p>
  if (receta.isError) return <Aviso>No pudimos cargar la receta. Recarga la página para intentarlo de nuevo.</Aviso>
  return (
    <>
      <Formulario key={receta.data?.id ?? 'nueva'} base={base} receta={receta.data} editable={editable} />
      {receta.data && <Costo base={base} />}
      {receta.data && <Versiones base={base} />}
    </>
  )
}

function Formulario({ base, receta, editable }: { base: string; receta: Receta | null; editable: boolean }) {
  const { avisar } = useAvisos()
  const cliente = useQueryClient()
  const insumos = useQuery({ queryKey: ['insumos'], queryFn: () => api<Insumo[]>('/insumos') })
  const [rendimiento, setRendimiento] = useState(receta ? dec(receta.rendimiento).toFixed() : '1')
  const [filas, setFilas] = useState<Fila[]>(
    receta?.items.map((i, n) => ({ clave: n, insumo_id: i.insumo_id, cantidad: dec(i.cantidad).toFixed() })) ?? [
      { clave: 0, insumo_id: '', cantidad: '' },
    ],
  )
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [error, setError] = useState<string>()
  const [guardando, setGuardando] = useState(false)
  const unidades = new Map((insumos.data ?? []).map((i) => [i.id, i.unidad_base]))

  function cambiar(clave: number, cambio: Partial<Fila>) {
    setFilas((f) => f.map((x) => (x.clave === clave ? { ...x, ...cambio } : x)))
  }

  async function guardar(ev: FormEvent) {
    ev.preventDefault()
    const e: Record<string, string> = {}
    const rinde = leerCantidad(rendimiento)
    if (!rinde || dec(rinde).lte(0)) e.rendimiento = 'Escribe cuántas unidades rinde, por ejemplo 12.'
    const usadas = new Set<string>()
    const items = filas.filter((f) => f.insumo_id || f.cantidad)
    for (const f of items) {
      const c = leerCantidad(f.cantidad)
      if (!f.insumo_id) e[`i${f.clave}`] = 'Elige el insumo.'
      else if (usadas.has(f.insumo_id)) e[`i${f.clave}`] = 'Este insumo ya está en la receta.'
      if (!c || dec(c).lte(0)) e[`c${f.clave}`] = 'Escribe la cantidad.'
      usadas.add(f.insumo_id)
    }
    if (items.length === 0) e.items = 'Agrega al menos un insumo.'
    setErrores(e)
    if (Object.keys(e).length || !rinde) return
    setGuardando(true)
    setError(undefined)
    try {
      const nueva = await api<Receta>(`${base}/receta`, {
        method: 'PUT',
        json: { rendimiento: rinde, items: items.map((f) => ({ insumo_id: f.insumo_id, cantidad: leerCantidad(f.cantidad) })) },
      })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['receta', base] }),
        cliente.invalidateQueries({ queryKey: ['costo', base] }),
        cliente.invalidateQueries({ queryKey: ['versiones', base] }),
        cliente.invalidateQueries({ queryKey: ['productos'] }),
        cliente.invalidateQueries({ queryKey: ['adiciones'] }),
      ])
      avisar(`Receta guardada: versión ${nueva.version}.`)
    } catch (err) {
      setError(mensajeDeError(err))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={guardar} noValidate>
      <p className="mb-4 text-sm text-cafe-medio">
        {receta
          ? `Versión ${receta.version} vigente desde el ${fechaCorta(new Date(receta.creado_en))}.`
          : 'Todavía no tiene receta.'}
        {editable && ' Al guardar se crea una versión nueva; lo ya producido no cambia.'}
      </p>
      <Campo
        etiqueta="Rinde (unidades)"
        inputMode="decimal"
        value={rendimiento}
        onChange={(e) => setRendimiento(e.target.value)}
        error={errores.rendimiento}
        disabled={!editable}
        className="max-w-40"
      />
      <fieldset className="mt-4">
        <legend className="mb-2 text-sm font-semibold">Insumos</legend>
        <ul className="flex flex-col gap-2.5">
          {filas.map((f) => (
            <li key={f.clave} className="grid grid-cols-[minmax(0,1fr)_7.5rem_auto] items-start gap-2">
              <div>
                <select
                  aria-label="Insumo"
                  value={f.insumo_id}
                  disabled={!editable}
                  onChange={(e) => cambiar(f.clave, { insumo_id: e.target.value })}
                  aria-invalid={errores[`i${f.clave}`] ? true : undefined}
                  className={unir(
                    'h-12 w-full rounded-control border bg-blanco px-3 text-base focus:border-dorado-borde focus:outline-none',
                    errores[`i${f.clave}`] ? 'border-peligro' : 'border-dorado-claro',
                  )}
                >
                  <option value="">Elige un insumo</option>
                  {insumos.data?.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.nombre}
                    </option>
                  ))}
                </select>
                {errores[`i${f.clave}`] && <p className="mt-1 text-sm text-peligro-texto">{errores[`i${f.clave}`]}</p>}
              </div>
              <div>
                <div className="relative">
                  <input
                    aria-label={`Cantidad${unidades.get(f.insumo_id) ? ` en ${unidades.get(f.insumo_id)}` : ''}`}
                    inputMode="decimal"
                    value={f.cantidad}
                    disabled={!editable}
                    onChange={(e) => cambiar(f.clave, { cantidad: e.target.value })}
                    aria-invalid={errores[`c${f.clave}`] ? true : undefined}
                    className={unir(
                      'h-12 w-full rounded-control border bg-blanco pr-11 pl-3 text-right text-base focus:border-dorado-borde focus:outline-none',
                      errores[`c${f.clave}`] ? 'border-peligro' : 'border-dorado-claro',
                    )}
                  />
                  <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-cafe-suave">
                    {unidades.get(f.insumo_id) ?? ''}
                  </span>
                </div>
                {errores[`c${f.clave}`] && <p className="mt-1 text-sm text-peligro-texto">{errores[`c${f.clave}`]}</p>}
              </div>
              {editable ? (
                <button
                  type="button"
                  aria-label="Quitar insumo"
                  title="Quitar insumo"
                  onClick={() => setFilas((x) => x.filter((y) => y.clave !== f.clave))}
                  className="grid size-12 place-items-center rounded-control text-cafe-suave hover:bg-peligro-fondo hover:text-peligro-texto"
                >
                  <Trash2 aria-hidden className="size-[18px]" />
                </button>
              ) : (
                <span className="size-12" />
              )}
            </li>
          ))}
        </ul>
        {errores.items && <p className="mt-2 text-sm text-peligro-texto">{errores.items}</p>}
        {editable && (
          <button
            type="button"
            onClick={() => setFilas((x) => [...x, { clave: Math.max(-1, ...x.map((y) => y.clave)) + 1, insumo_id: '', cantidad: '' }])}
            className="mt-2.5 inline-flex h-10 items-center gap-1.5 rounded-control px-3 font-semibold text-fucsia hover:bg-rosa-suave"
          >
            <Plus aria-hidden className="size-[18px]" strokeWidth={2.2} />
            Agregar insumo
          </button>
        )}
      </fieldset>
      {error && (
        <div className="mt-4">
          <Aviso>{error}</Aviso>
        </div>
      )}
      {editable && (
        <Boton type="submit" disabled={guardando} className="mt-5 w-full">
          {guardando ? 'Guardando…' : receta ? 'Guardar nueva versión' : 'Guardar receta'}
        </Boton>
      )}
    </form>
  )
}

/** Panel de costo teórico con el último costo de compra y el margen frente al precio. */
function Costo({ base }: { base: string }) {
  const costo = useQuery({ queryKey: ['costo', base], queryFn: () => api<CostoReceta>(`${base}/costo`) })
  const c = costo.data
  if (!c) return null
  const porcentaje = c.margen_porcentaje !== null ? dec(c.margen_porcentaje) : null
  const bajo = porcentaje !== null && porcentaje.lt(MARGEN_MINIMO)
  const sinCosto = c.items.filter((i) => i.costo === null).map((i) => i.insumo)
  return (
    <section aria-label="Costo y margen" className="mt-6 rounded-tarjeta border border-linea p-4">
      <h3 className="font-serif text-[24px] leading-tight font-medium">Costo teórico</h3>
      <p className="mt-1 text-sm text-cafe-suave">Con el último costo de compra de cada insumo. El costo real sale por lote.</p>
      <dl className="mt-3 divide-y divide-linea text-[15px]">
        {c.items.map((i) => (
          <div key={i.insumo_id} className="flex justify-between gap-3 py-1.5">
            <dt className="min-w-0 text-cafe-medio">
              {i.insumo} · {cantidadLegible(i.cantidad, i.unidad)}
            </dt>
            <dd className="shrink-0">{i.costo === null ? 'Sin costo' : pesos(i.costo)}</dd>
          </div>
        ))}
        <div className="flex justify-between gap-3 py-1.5 font-semibold">
          <dt>Costo de la receta (rinde {textoCantidad(c.rendimiento)})</dt>
          <dd>{pesos(c.costo_receta)}</dd>
        </div>
        <div className="flex justify-between gap-3 py-1.5">
          <dt className="text-cafe-medio">Costo por unidad</dt>
          <dd>{pesos(c.costo_por_unidad)}</dd>
        </div>
        <div className="flex justify-between gap-3 py-1.5">
          <dt className="text-cafe-medio">Precio de venta</dt>
          <dd>{pesos(c.precio)}</dd>
        </div>
        <div className={unir('flex justify-between gap-3 py-1.5 font-semibold', bajo && 'text-peligro-texto')}>
          <dt>Margen</dt>
          <dd>
            {pesos(c.margen)}
            {porcentaje !== null && ` · ${textoCantidad(porcentaje.toDecimalPlaces(1).toFixed())} %`}
          </dd>
        </div>
      </dl>
      {sinCosto.length > 0 && (
        <div className="mt-3">
          <Aviso tono="aviso">
            {sinCosto.join(', ')} {sinCosto.length === 1 ? 'nunca se ha comprado' : 'nunca se han comprado'}: el costo
            está incompleto hasta registrar una compra.
          </Aviso>
        </div>
      )}
      {bajo && (
        <div className="mt-3">
          <Aviso>
            El margen está por debajo del {MARGEN_MINIMO} %. Revisa el precio o la receta.
          </Aviso>
        </div>
      )}
    </section>
  )
}

function Versiones({ base }: { base: string }) {
  const versiones = useQuery({
    queryKey: ['versiones', base],
    queryFn: () => api<Receta[]>(`${base}/receta/versiones`),
  })
  const anteriores = (versiones.data ?? []).filter((v) => !v.vigente)
  if (anteriores.length === 0) return null
  return (
    <section aria-label="Versiones anteriores" className="mt-6">
      <h3 className="text-sm font-semibold">Versiones anteriores</h3>
      <ul className="mt-2 flex flex-col gap-2">
        {anteriores.map((v) => (
          <li key={v.id}>
            <details className="rounded-control border border-linea px-4 py-2.5">
              <summary className="cursor-pointer text-[15px]">
                Versión {v.version} · {fechaCorta(new Date(v.creado_en))} · rinde {textoCantidad(v.rendimiento)}
              </summary>
              <ul className="mt-2 text-sm text-cafe-medio">
                {v.items.map((i) => (
                  <li key={i.insumo_id}>
                    {i.insumo}: {cantidadLegible(i.cantidad, i.unidad)}
                  </li>
                ))}
              </ul>
            </details>
          </li>
        ))}
      </ul>
    </section>
  )
}
