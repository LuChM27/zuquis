import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { FiltroLista } from '../../components/Buscador'
import { Aviso, Celda, FilaTabla, Interruptor, ListaDetalle, PanelDetalle, Selector, Tabla, Vacio } from '../../components/formulario'
import { Boton, Campo, Chip } from '../../components/ui'
import { api } from '../../lib/api'
import { coincide } from '../../lib/buscar'
import { dec } from '../../lib/decimal'
import type { Insumo, Presentacion } from '../../lib/tipos'
import { cantidadLegible } from '../../lib/unidades'
import { mensajeDeError, useSeleccion } from '../configuracion/acciones'
import { PieFormulario, TarjetaLista } from '../configuracion/comun'
import { leerCantidad } from '../inventario/comun'

const UNIDADES: Record<string, string> = { g: 'Gramos (g)', ml: 'Mililitros (ml)', und: 'Unidades (und)' }

export function Insumos() {
  const insumos = useQuery({
    queryKey: ['insumos', 'todos'],
    queryFn: () => api<Insumo[]>('/insumos?incluir_inactivos=true'),
  })
  const { sel, version, elegir, fijar } = useSeleccion()
  const [busqueda, setBusqueda] = useState('')
  const todos = insumos.data ?? []
  const lista = todos.filter((i) => coincide(i.nombre, busqueda))
  const actual = sel === 'nuevo' ? null : (lista.find((i) => i.id === sel) ?? lista[0] ?? null)
  const modo = sel === 'nuevo' || (!actual && insumos.isSuccess && todos.length === 0) ? 'nuevo' : actual

  return (
    <ListaDetalle
      lista={
        <TarjetaLista titulo="Insumos" nuevo="Nuevo insumo" alNuevo={() => elegir('nuevo')}>
          {todos.length > 0 && <FiltroLista etiqueta="Buscar insumo" valor={busqueda} alCambiar={setBusqueda} className="mb-4 max-w-sm" />}
          {insumos.isError && <Aviso>No pudimos cargar los insumos. Recarga la página para intentarlo de nuevo.</Aviso>}
          {insumos.isSuccess && lista.length === 0 && <Vacio>{todos.length ? 'Ningún insumo coincide.' : 'Todavía no hay insumos.'}</Vacio>}
          {lista.length > 0 && (
            <Tabla columnas={[{ texto: 'Insumo' }, { texto: 'Se compra en', ocultarMovil: true }, { texto: 'Mínimo', derecha: true }, { texto: 'Estado' }]}>
              {lista.map((i) => (
                <FilaTabla key={i.id} seleccionada={modo !== 'nuevo' && actual?.id === i.id} alElegir={() => elegir(i.id)}>
                  <Celda className="font-semibold">{i.nombre}</Celda>
                  <Celda ocultarMovil className="text-cafe-medio">
                    {i.presentaciones.filter((p) => p.activa).map((p) => p.nombre).join(', ') || i.unidad_base}
                  </Celda>
                  <Celda derecha className="whitespace-nowrap">{cantidadLegible(i.stock_minimo, i.unidad_base)}</Celda>
                  <Celda>{i.activo ? <Chip tono="exito">Activo</Chip> : <Chip>Inactivo</Chip>}</Celda>
                </FilaTabla>
              ))}
            </Tabla>
          )}
        </TarjetaLista>
      }
      detalle={
        modo ? (
          <PanelDetalle rotulo={modo === 'nuevo' ? 'Nuevo' : 'Insumo'} titulo={modo === 'nuevo' ? 'Nuevo insumo' : modo.nombre}>
            <FormInsumo key={`${version}-${modo === 'nuevo' ? 'n' : modo.id}`} insumo={modo === 'nuevo' ? null : modo} alGuardar={(i) => fijar(i.id)} />
          </PanelDetalle>
        ) : null
      }
    />
  )
}

function FormInsumo({ insumo, alGuardar }: { insumo: Insumo | null; alGuardar: (i: Insumo) => void }) {
  const cliente = useQueryClient()
  const nuevo = insumo === null
  const [nombre, setNombre] = useState(insumo?.nombre ?? '')
  const [unidad, setUnidad] = useState(insumo?.unidad_base ?? 'g')
  const [minimo, setMinimo] = useState(insumo ? dec(insumo.stock_minimo).toFixed() : '0')
  const [dias, setDias] = useState(insumo?.dias_alerta_vencimiento?.toString() ?? '')
  const [activo, setActivo] = useState(insumo?.activo ?? true)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [error, setError] = useState<string>()
  const [guardando, setGuardando] = useState(false)
  const [guardado, setGuardado] = useState(false)

  async function enviar(ev: FormEvent) {
    ev.preventDefault()
    const e: Record<string, string> = {}
    const min = leerCantidad(minimo)
    if (nombre.trim().length < 2) e.nombre = 'Escribe el nombre del insumo (mínimo 2 letras).'
    if (min === null) e.minimo = `Escribe el mínimo en ${unidad}, por ejemplo 5000.`
    if (dias && !/^\d{1,3}$/.test(dias)) e.dias = 'Escribe los días como número, o déjalo vacío.'
    setErrores(e)
    setGuardado(false)
    if (Object.keys(e).length) return
    setGuardando(true)
    setError(undefined)
    const cuerpo = {
      nombre: nombre.trim(),
      unidad_base: unidad,
      stock_minimo: min,
      dias_alerta_vencimiento: dias ? Number(dias) : null,
      ...(nuevo ? {} : { activo }),
    }
    try {
      const i = nuevo
        ? await api<Insumo>('/insumos', { method: 'POST', json: cuerpo })
        : await api<Insumo>(`/insumos/${insumo.id}`, { method: 'PATCH', json: cuerpo })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['insumos'] }),
        cliente.invalidateQueries({ queryKey: ['inventario'] }),
      ])
      setGuardado(true)
      alGuardar(i)
    } catch (err) {
      setError(mensajeDeError(err))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <>
    <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
      <Campo etiqueta="Nombre" value={nombre} maxLength={120} onChange={(e) => setNombre(e.target.value)} error={errores.nombre} />
      <Selector etiqueta="Unidad base" value={unidad} onChange={(e) => setUnidad(e.target.value)}>
        {Object.entries(UNIDADES).map(([v, t]) => (
          <option key={v} value={v}>
            {t}
          </option>
        ))}
      </Selector>
      <p className="-mt-2 text-sm text-cafe-suave">
        Recetas, inventario y costos se llevan en esta unidad. No se puede cambiar cuando el insumo ya tiene movimientos.
      </p>
      <div className="grid grid-cols-2 gap-3">
        <Campo etiqueta={`Mínimo (${unidad})`} inputMode="decimal" value={minimo} onChange={(e) => setMinimo(e.target.value)} error={errores.minimo} />
        <Campo etiqueta="Avisar vencimiento (días)" inputMode="numeric" placeholder="General" value={dias} onChange={(e) => setDias(e.target.value)} error={errores.dias} />
      </div>
      {!nuevo && <Interruptor etiqueta="Activo" ayuda="Inactivo: no aparece para comprar ni en recetas nuevas." activo={activo} alCambiar={setActivo} />}
      {error && <Aviso>{error}</Aviso>}
      {guardado && !error && <p role="status" className="text-sm font-semibold text-exito-texto">Cambios guardados.</p>}
      <PieFormulario>
        <Boton type="submit" disabled={guardando}>
          {guardando ? 'Guardando…' : nuevo ? 'Crear insumo' : 'Guardar cambios'}
        </Boton>
      </PieFormulario>
    </form>
    {/* Las presentaciones usan la unidad elegida en el formulario, aunque aún no se guarde. */}
    {!nuevo && <Presentaciones insumo={insumo} unidad={unidad} />}
    </>
  )
}

/** Unidades de compra: "Bulto 50 kg" = 50.000 g. */
function Presentaciones({ insumo, unidad }: { insumo: Insumo; unidad: string }) {
  const cliente = useQueryClient()
  const [nombre, setNombre] = useState('')
  const [factor, setFactor] = useState('')
  const [error, setError] = useState<string>()
  const [guardando, setGuardando] = useState(false)

  async function refrescar() {
    await cliente.invalidateQueries({ queryKey: ['insumos'] })
  }

  async function agregar(ev: FormEvent) {
    ev.preventDefault()
    const f = leerCantidad(factor)
    if (nombre.trim().length < 1 || !f || dec(f).lte(0)) {
      setError(`Escribe el nombre (por ejemplo "Bulto 50 kg") y cuántos ${unidad} trae.`)
      return
    }
    setGuardando(true)
    setError(undefined)
    try {
      await api(`/insumos/${insumo.id}/presentaciones`, { method: 'POST', json: { nombre: nombre.trim(), factor: f } })
      await refrescar()
      setNombre('')
      setFactor('')
    } catch (err) {
      setError(mensajeDeError(err))
    } finally {
      setGuardando(false)
    }
  }

  async function alternar(p: Presentacion) {
    try {
      await api(`/insumos/${insumo.id}/presentaciones/${p.id}`, { method: 'PATCH', json: { activa: !p.activa } })
      await refrescar()
    } catch (err) {
      setError(mensajeDeError(err))
    }
  }

  return (
    <section aria-label="Presentaciones" className="mt-6 border-t border-linea pt-5">
      <h3 className="font-serif text-[24px] leading-tight font-medium">Presentaciones</h3>
      <p className="mt-1 text-sm text-cafe-suave">Cómo se compra. Al registrar una compra se convierte a {unidad}.</p>
      {unidad !== insumo.unidad_base && insumo.presentaciones.length > 0 && (
        <div className="mt-3">
          <Aviso tono="aviso">
            Cambiaste la unidad de {insumo.unidad_base} a {unidad}. Guarda los cambios y revisa que cada presentación diga
            cuántos {unidad} trae.
          </Aviso>
        </div>
      )}
      <ul className="mt-3 flex flex-col divide-y divide-linea">
        {insumo.presentaciones.map((p) => (
          <li key={p.id} className="flex items-center justify-between gap-3 py-2">
            <span className={p.activa ? '' : 'text-cafe-suave line-through'}>
              <span className="font-semibold">{p.nombre}</span>
              <span className="block text-sm text-cafe-suave">= {cantidadLegible(p.factor, unidad)}</span>
            </span>
            <button type="button" onClick={() => alternar(p)} className="h-10 rounded-control px-3 text-sm font-semibold text-fucsia hover:bg-rosa-suave">
              {p.activa ? 'Desactivar' : 'Activar'}
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={agregar} noValidate className="mt-3 grid grid-cols-[minmax(0,1fr)_6.5rem] gap-2">
        <Campo etiqueta="Nueva presentación" placeholder="Bulto 50 kg" value={nombre} maxLength={80} onChange={(e) => setNombre(e.target.value)} />
        <Campo etiqueta={`Trae (${unidad})`} inputMode="decimal" value={factor} onChange={(e) => setFactor(e.target.value)} />
        {error && (
          <div className="col-span-2">
            <Aviso>{error}</Aviso>
          </div>
        )}
        <button
          type="submit"
          disabled={guardando}
          className="col-span-2 inline-flex h-10 items-center gap-1.5 justify-self-start rounded-control px-3 font-semibold text-fucsia hover:bg-rosa-suave disabled:opacity-60"
        >
          <Plus aria-hidden className="size-[18px]" strokeWidth={2.2} />
          Agregar presentación
        </button>
      </form>
    </section>
  )
}
