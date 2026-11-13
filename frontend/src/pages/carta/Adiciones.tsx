import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useSesion } from '../../auth/contexto'
import { CampoDinero } from '../../components/CampoDinero'
import { Aviso, Casilla, Celda, FilaTabla, Interruptor, ListaDetalle, PanelDetalle, Pildoras, Tabla, Vacio } from '../../components/formulario'
import { Boton, Campo, Chip } from '../../components/ui'
import { api } from '../../lib/api'
import { pesos } from '../../lib/formato'
import type { Adicion, Producto } from '../../lib/tipos'
import { mensajeDeError, useSeleccion } from '../configuracion/acciones'
import { PieFormulario, TarjetaLista } from '../configuracion/comun'
import { EditorReceta } from './EditorReceta'

export function Adiciones() {
  const { puede } = useSesion()
  const editor = puede('carta.editar')
  const adiciones = useQuery({
    queryKey: ['adiciones', 'todas'],
    queryFn: () => api<Adicion[]>('/modificadores?incluir_inactivos=true'),
  })
  const productos = useQuery({ queryKey: ['productos', 'todos'], queryFn: () => api<Producto[]>('/productos?incluir_inactivos=true') })
  const { sel, version, elegir, fijar } = useSeleccion()
  const lista = adiciones.data ?? []
  const actual = sel === 'nuevo' ? null : (lista.find((a) => a.id === sel) ?? lista[0] ?? null)
  const modo = editor && (sel === 'nuevo' || (!actual && adiciones.isSuccess)) ? 'nuevo' : actual
  const usos = (id: string) => (productos.data ?? []).filter((p) => p.modificadores.some((m) => m.id === id))

  return (
    <ListaDetalle
      lista={
        <TarjetaLista titulo="Adiciones" nuevo={editor ? 'Nueva adición' : undefined} alNuevo={() => elegir('nuevo')}>
          {adiciones.isError && <Aviso>No pudimos cargar las adiciones. Recarga la página para intentarlo de nuevo.</Aviso>}
          {adiciones.isSuccess && lista.length === 0 && <Vacio>Todavía no hay adiciones, como queso extra o bola de helado.</Vacio>}
          {lista.length > 0 && (
            <Tabla columnas={[{ texto: 'Adición' }, { texto: 'Se ofrece en', ocultarMovil: true }, { texto: 'Precio', derecha: true }, { texto: 'Estado' }]}>
              {lista.map((a) => (
                <FilaTabla key={a.id} seleccionada={modo !== 'nuevo' && actual?.id === a.id} alElegir={() => elegir(a.id)}>
                  <Celda className="font-semibold">{a.nombre}</Celda>
                  <Celda ocultarMovil className="text-cafe-medio">
                    {usos(a.id).length} {usos(a.id).length === 1 ? 'producto' : 'productos'}
                  </Celda>
                  <Celda derecha className="font-semibold">{pesos(a.precio)}</Celda>
                  <Celda>
                    <span className="flex flex-wrap gap-1.5">
                      {a.activo ? <Chip tono="exito">Activa</Chip> : <Chip>Inactiva</Chip>}
                      {!a.tiene_receta && <Chip tono="aviso">Sin receta</Chip>}
                    </span>
                  </Celda>
                </FilaTabla>
              ))}
            </Tabla>
          )}
        </TarjetaLista>
      }
      detalle={
        modo ? (
          <DetalleAdicion
            key={`${modo === 'nuevo' ? 'n' : modo.id}-${version}`}
            adicion={modo === 'nuevo' ? null : modo}
            productos={productos.data ?? []}
            alGuardar={(a) => fijar(a.id)}
          />
        ) : null
      }
    />
  )
}

function DetalleAdicion({
  adicion,
  productos,
  alGuardar,
}: {
  adicion: Adicion | null
  productos: Producto[]
  alGuardar: (a: Adicion) => void
}) {
  const { puede } = useSesion()
  const editor = puede('carta.editar')
  const [pestana, setPestana] = useState<'datos' | 'receta'>(editor ? 'datos' : 'receta')
  return (
    <PanelDetalle
      rotulo={adicion ? 'Adición' : 'Nueva'}
      titulo={adicion?.nombre ?? 'Nueva adición'}
      subtitulo={adicion ? pesos(adicion.precio) : undefined}
    >
      {adicion && (
        <div className="mb-5">
          <Pildoras
            etiqueta="Qué ver de la adición"
            valor={pestana}
            alCambiar={setPestana}
            opciones={[
              { valor: 'datos', texto: 'Datos' },
              { valor: 'receta', texto: 'Receta' },
            ]}
          />
        </div>
      )}
      {(pestana === 'datos' || !adicion) &&
        (editor ? (
          <FormAdicion adicion={adicion} productos={productos} alGuardar={alGuardar} />
        ) : (
          <p className="text-cafe-medio">
            Se ofrece en: {productos.filter((p) => p.modificadores.some((m) => m.id === adicion?.id)).map((p) => p.nombre).join(', ') || 'ningún producto'}.
          </p>
        ))}
      {pestana === 'receta' && adicion && <EditorReceta base={`/modificadores/${adicion.id}`} editable={puede('recetas.editar')} />}
    </PanelDetalle>
  )
}

function FormAdicion({
  adicion,
  productos,
  alGuardar,
}: {
  adicion: Adicion | null
  productos: Producto[]
  alGuardar: (a: Adicion) => void
}) {
  const cliente = useQueryClient()
  const nueva = adicion === null
  const usaba = new Set(productos.filter((p) => adicion && p.modificadores.some((m) => m.id === adicion.id)).map((p) => p.id))
  const [nombre, setNombre] = useState(adicion?.nombre ?? '')
  const [precio, setPrecio] = useState<number | null>(adicion?.precio ?? null)
  const [activo, setActivo] = useState(adicion?.activo ?? true)
  const [enProductos, setEnProductos] = useState<Set<string>>(usaba)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [error, setError] = useState<string>()
  const [guardando, setGuardando] = useState(false)
  const [guardado, setGuardado] = useState(false)

  async function enviar(ev: FormEvent) {
    ev.preventDefault()
    const e: Record<string, string> = {}
    if (nombre.trim().length < 2) e.nombre = 'Escribe el nombre (mínimo 2 letras).'
    if (precio === null) e.precio = 'Escribe el precio; puede ser $0.'
    setErrores(e)
    setGuardado(false)
    if (Object.keys(e).length) return
    setGuardando(true)
    setError(undefined)
    try {
      const a = nueva
        ? await api<Adicion>('/modificadores', { method: 'POST', json: { nombre: nombre.trim(), precio } })
        : await api<Adicion>(`/modificadores/${adicion.id}`, { method: 'PATCH', json: { nombre: nombre.trim(), precio, activo } })
      // A qué productos aplica se guarda en cada producto: solo se tocan los que cambiaron.
      const cambios = productos.filter((p) => enProductos.has(p.id) !== usaba.has(p.id))
      await Promise.all(
        cambios.map((p) => {
          const ids = p.modificadores.map((m) => m.id).filter((id) => id !== a.id)
          return api(`/productos/${p.id}`, {
            method: 'PATCH',
            json: { modificador_ids: enProductos.has(p.id) ? [...ids, a.id] : ids },
          })
        }),
      )
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['adiciones'] }),
        cliente.invalidateQueries({ queryKey: ['productos'] }),
      ])
      setGuardado(true)
      alGuardar(a)
    } catch (err) {
      setError(mensajeDeError(err))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
      <Campo etiqueta="Nombre" value={nombre} maxLength={80} onChange={(e) => setNombre(e.target.value)} error={errores.nombre} />
      <CampoDinero etiqueta="Precio" valor={precio} alCambiar={setPrecio} error={errores.precio} />
      {!nueva && <Interruptor etiqueta="Activa" activo={activo} alCambiar={setActivo} />}
      {productos.length > 0 && (
        <fieldset>
          <legend className="mb-1 text-sm font-semibold">Se ofrece en</legend>
          <div className="max-h-64 overflow-y-auto rounded-control border border-linea px-3 py-1">
            {productos
              .filter((p) => p.activo)
              .map((p) => (
                <Casilla
                  key={p.id}
                  etiqueta={p.nombre}
                  marcada={enProductos.has(p.id)}
                  alCambiar={(v) =>
                    setEnProductos((s) => {
                      const n = new Set(s)
                      if (v) n.add(p.id)
                      else n.delete(p.id)
                      return n
                    })
                  }
                />
              ))}
          </div>
        </fieldset>
      )}
      {error && <Aviso>{error}</Aviso>}
      {guardado && !error && <p role="status" className="text-sm font-semibold text-exito-texto">Cambios guardados.</p>}
      <PieFormulario>
        <Boton type="submit" disabled={guardando}>
          {guardando ? 'Guardando…' : nueva ? 'Crear adición' : 'Guardar cambios'}
        </Boton>
      </PieFormulario>
    </form>
  )
}
