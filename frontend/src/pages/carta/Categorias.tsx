import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronUp, GripVertical } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Aviso, Interruptor, ListaDetalle, PanelDetalle, Vacio } from '../../components/formulario'
import { Boton, Campo, Chip } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api } from '../../lib/api'
import { unir } from '../../lib/clases'
import type { Categoria } from '../../lib/tipos'
import { mensajeDeError, useGuardar, useSeleccion } from '../configuracion/acciones'
import { PieFormulario, TarjetaLista } from '../configuracion/comun'
import { IconoCategoria } from './comun'
import { ICONOS, mover } from './utilidades'

export function Categorias() {
  const cliente = useQueryClient()
  const { avisar } = useAvisos()
  const categorias = useQuery({
    queryKey: ['categorias', 'todas'],
    queryFn: () => api<Categoria[]>('/categorias?incluir_inactivas=true'),
  })
  const { sel, version, elegir, fijar } = useSeleccion()
  const [arrastrada, setArrastrada] = useState<number | null>(null)
  const [orden, setOrden] = useState<Categoria[] | null>(null)
  const lista = orden ?? [...(categorias.data ?? [])].sort((a, b) => a.orden - b.orden)
  const actual = sel === 'nuevo' ? null : (lista.find((c) => c.id === sel) ?? lista[0] ?? null)
  const modo = sel === 'nuevo' || (!actual && categorias.isSuccess) ? 'nuevo' : actual

  /** Guarda el orden nuevo: solo las categorías que cambiaron de posición. */
  async function guardarOrden(nueva: Categoria[]) {
    setOrden(nueva)
    try {
      await Promise.all(
        nueva.map((c, i) =>
          c.orden === i + 1 ? null : api(`/categorias/${c.id}`, { method: 'PATCH', json: { orden: i + 1 } }),
        ),
      )
      await cliente.invalidateQueries({ queryKey: ['categorias'] })
      avisar('Orden guardado. Así aparecen en el punto de venta.')
    } catch (e) {
      avisar(mensajeDeError(e), 'error')
    } finally {
      setOrden(null)
    }
  }

  return (
    <ListaDetalle
      lista={
        <TarjetaLista titulo="Categorías" nuevo="Nueva categoría" alNuevo={() => elegir('nuevo')}>
          <p className="mb-3 text-sm text-cafe-suave">Arrastra para cambiar el orden en que salen en el punto de venta.</p>
          {categorias.isError && <Aviso>No pudimos cargar las categorías. Recarga la página para intentarlo de nuevo.</Aviso>}
          {categorias.isSuccess && lista.length === 0 && <Vacio>Todavía no hay categorías.</Vacio>}
          <ol aria-label="Categorías en orden" className="flex flex-col">
            {lista.map((c, i) => (
              <li
                key={c.id}
                draggable
                onDragStart={() => setArrastrada(i)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => {
                  if (arrastrada !== null && arrastrada !== i) guardarOrden(mover(lista, arrastrada, i))
                  setArrastrada(null)
                }}
                onDragEnd={() => setArrastrada(null)}
                className={unir(
                  'flex items-center gap-2 border-b border-linea py-1.5 last:border-b-0',
                  arrastrada === i && 'opacity-50',
                )}
              >
                <GripVertical aria-hidden className="size-5 shrink-0 cursor-grab text-cafe-suave" />
                <button
                  type="button"
                  onClick={() => elegir(c.id)}
                  aria-current={modo !== 'nuevo' && actual?.id === c.id ? true : undefined}
                  className={unir(
                    'flex min-h-12 min-w-0 flex-1 items-center gap-3 rounded-control px-2 text-left',
                    modo !== 'nuevo' && actual?.id === c.id ? 'bg-rosa-suave/60' : 'hover:bg-crema',
                  )}
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-full bg-rosa-suave text-fucsia-oscuro">
                    <IconoCategoria icono={c.icono} className="size-[18px]" />
                  </span>
                  <span className="min-w-0 flex-1 truncate font-semibold">{c.nombre}</span>
                  {!c.activa && <Chip>Inactiva</Chip>}
                </button>
                <span className="flex shrink-0">
                  <button
                    type="button"
                    aria-label={`Subir ${c.nombre}`}
                    title="Subir"
                    disabled={i === 0}
                    onClick={() => guardarOrden(mover(lista, i, i - 1))}
                    className="grid size-10 place-items-center rounded-control text-cafe-suave hover:bg-crema disabled:opacity-30"
                  >
                    <ChevronUp aria-hidden className="size-5" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Bajar ${c.nombre}`}
                    title="Bajar"
                    disabled={i === lista.length - 1}
                    onClick={() => guardarOrden(mover(lista, i, i + 1))}
                    className="grid size-10 place-items-center rounded-control text-cafe-suave hover:bg-crema disabled:opacity-30"
                  >
                    <ChevronDown aria-hidden className="size-5" />
                  </button>
                </span>
              </li>
            ))}
          </ol>
        </TarjetaLista>
      }
      detalle={
        modo ? (
          <PanelDetalle rotulo={modo === 'nuevo' ? 'Nueva' : 'Categoría'} titulo={modo === 'nuevo' ? 'Nueva categoría' : modo.nombre}>
            <FormCategoria
              key={version}
              categoria={modo === 'nuevo' ? null : modo}
              siguienteOrden={lista.length + 1}
              alGuardar={(c) => fijar(c.id)}
            />
          </PanelDetalle>
        ) : null
      }
    />
  )
}

function FormCategoria({
  categoria,
  siguienteOrden,
  alGuardar,
}: {
  categoria: Categoria | null
  siguienteOrden: number
  alGuardar: (c: Categoria) => void
}) {
  const nueva = categoria === null
  const [nombre, setNombre] = useState(categoria?.nombre ?? '')
  const [icono, setIcono] = useState(categoria?.icono ?? 'cake-slice')
  const [activa, setActiva] = useState(categoria?.activa ?? true)
  const [error, setError] = useState<string>()
  const [guardado, setGuardado] = useState(false)
  const guardar = useGuardar(
    (cuerpo: Record<string, unknown>) =>
      nueva
        ? api<Categoria>('/categorias', { method: 'POST', json: { ...cuerpo, orden: siguienteOrden } })
        : api<Categoria>(`/categorias/${categoria.id}`, { method: 'PATCH', json: cuerpo }),
    [['categorias']],
    (c) => {
      setGuardado(true)
      alGuardar(c)
    },
  )

  function enviar(ev: FormEvent) {
    ev.preventDefault()
    setGuardado(false)
    if (nombre.trim().length < 2) return setError('Escribe el nombre de la categoría (mínimo 2 letras).')
    setError(undefined)
    guardar.mutate({ nombre: nombre.trim(), icono, ...(nueva ? {} : { activa }) })
  }

  return (
    <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
      <Campo etiqueta="Nombre" value={nombre} maxLength={80} onChange={(e) => setNombre(e.target.value)} error={error} />
      <fieldset>
        <legend className="mb-1.5 text-sm font-semibold">Ícono</legend>
        <div className="grid grid-cols-6 gap-1.5">
          {Object.entries(ICONOS).map(([clave, { icono: Icono, nombre: n }]) => (
            <label
              key={clave}
              title={n}
              className={unir(
                'grid aspect-square cursor-pointer place-items-center rounded-control border has-focus-visible:outline-2 has-focus-visible:outline-fucsia',
                icono === clave ? 'border-fucsia bg-rosa-suave text-fucsia-oscuro' : 'border-linea hover:border-dorado-claro',
              )}
            >
              <input type="radio" name="icono" value={clave} checked={icono === clave} onChange={() => setIcono(clave)} className="sr-only" aria-label={n} />
              <Icono aria-hidden className="size-5" strokeWidth={1.7} />
            </label>
          ))}
        </div>
      </fieldset>
      {!nueva && (
        <Interruptor etiqueta="Activa" ayuda="Inactiva: no aparece en el punto de venta." activo={activa} alCambiar={setActiva} />
      )}
      {guardar.error && <Aviso>{guardar.error}</Aviso>}
      {guardado && !guardar.error && <p role="status" className="text-sm font-semibold text-exito-texto">Cambios guardados.</p>}
      <PieFormulario>
        <Boton type="submit" disabled={guardar.isPending}>
          {guardar.isPending ? 'Guardando…' : nueva ? 'Crear categoría' : 'Guardar cambios'}
        </Boton>
      </PieFormulario>
    </form>
  )
}
