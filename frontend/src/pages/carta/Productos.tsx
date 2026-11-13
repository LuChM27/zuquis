import { useQuery } from '@tanstack/react-query'
import { ImagePlus } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { useSesion } from '../../auth/contexto'
import { CasillasConBusqueda, FiltroLista } from '../../components/Buscador'
import { CampoDinero } from '../../components/CampoDinero'
import { coincide } from '../../lib/buscar'
import { Aviso, Celda, FilaTabla, Interruptor, ListaDetalle, PanelDetalle, Pildoras, Selector, Tabla, Vacio } from '../../components/formulario'
import { Boton, Campo, Chip } from '../../components/ui'
import { api } from '../../lib/api'
import { cantidad as textoCantidad, dec } from '../../lib/decimal'
import { fechaCorta, hora, pesos } from '../../lib/formato'
import type { Adicion, CambioPrecio, Categoria, Producto, TipoProducto } from '../../lib/tipos'
import { useGuardar, useSeleccion } from '../configuracion/acciones'
import { PieFormulario, TarjetaLista } from '../configuracion/comun'
import { leerCantidad } from '../inventario/comun'
import { IconoCategoria } from './comun'
import { useImagen } from './utilidades'
import { EditorReceta } from './EditorReceta'

type Pestana = 'datos' | 'receta' | 'precios'

const TIPOS: Record<TipoProducto, { texto: string; ayuda: string }> = {
  preparado: { texto: 'Se prepara al momento', ayuda: 'Al venderlo se descuenta su receta.' },
  lote: { texto: 'Producido por lote', ayuda: 'Tiene unidades en vitrina que entran con cada producción.' },
}

export function Productos() {
  const { puede } = useSesion()
  const editor = puede('carta.editar')
  const [categoria, setCategoria] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const categorias = useQuery({ queryKey: ['categorias'], queryFn: () => api<Categoria[]>('/categorias') })
  const productos = useQuery({
    queryKey: ['productos', 'todos'],
    queryFn: () => api<Producto[]>('/productos?incluir_inactivos=true'),
  })
  const { sel, version, elegir, fijar } = useSeleccion()
  const nombresCategoria = new Map((categorias.data ?? []).map((c) => [c.id, c]))
  const lista = (productos.data ?? []).filter((p) => (!categoria || p.categoria_id === categoria) && coincide(p.nombre, busqueda))
  const actual = sel === 'nuevo' ? null : (lista.find((p) => p.id === sel) ?? lista[0] ?? null)
  const modo = editor && (sel === 'nuevo' || (!actual && productos.isSuccess && productos.data.length === 0)) ? 'nuevo' : actual

  return (
    <ListaDetalle
      lista={
        <TarjetaLista titulo="Productos" nuevo={editor ? 'Nuevo producto' : undefined} alNuevo={() => elegir('nuevo')}>
          <div className="mb-4 grid items-end gap-3 sm:grid-cols-2">
          <FiltroLista etiqueta="Buscar producto" valor={busqueda} alCambiar={setBusqueda} />
          <Selector etiqueta="Categoría" value={categoria} onChange={(e) => setCategoria(e.target.value)}>
            <option value="">Todas</option>
            {categorias.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </Selector>
          </div>
          {productos.isError && <Aviso>No pudimos cargar los productos. Recarga la página para intentarlo de nuevo.</Aviso>}
          {productos.isSuccess && lista.length === 0 && <Vacio>No hay productos que coincidan.</Vacio>}
          {lista.length > 0 && (
            <Tabla
              columnas={[
                { texto: 'Producto' },
                { texto: 'Tipo', ocultarMovil: true },
                { texto: 'Precio', derecha: true },
                { texto: 'Estado' },
              ]}
            >
              {lista.map((p) => (
                <FilaTabla key={p.id} seleccionada={modo !== 'nuevo' && actual?.id === p.id} alElegir={() => elegir(p.id)}>
                  <Celda>
                    <span className="flex items-center gap-3">
                      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-rosa-suave text-fucsia-oscuro">
                        <IconoCategoria icono={nombresCategoria.get(p.categoria_id)?.icono ?? null} className="size-[18px]" />
                      </span>
                      <span className="min-w-0">
                        <span className="block font-semibold">{p.nombre}</span>
                        <span className="block text-sm text-cafe-suave">{nombresCategoria.get(p.categoria_id)?.nombre}</span>
                      </span>
                    </span>
                  </Celda>
                  <Celda ocultarMovil className="text-cafe-medio">
                    {p.tipo === 'preparado' ? 'Se prepara' : `Por lote · ${textoCantidad(p.stock ?? '0')} en vitrina`}
                  </Celda>
                  <Celda derecha className="font-semibold whitespace-nowrap">
                    {pesos(p.precio)}
                  </Celda>
                  <Celda>
                    <span className="flex flex-wrap gap-1.5">
                      {!p.activo ? (
                        <Chip>Inactivo</Chip>
                      ) : p.disponible ? (
                        <Chip tono="exito">Disponible</Chip>
                      ) : (
                        <Chip tono="peligro">Agotado</Chip>
                      )}
                      {!p.tiene_receta && <Chip tono="aviso">Sin receta</Chip>}
                    </span>
                  </Celda>
                </FilaTabla>
              ))}
            </Tabla>
          )}
        </TarjetaLista>
      }
      detalle={
        modo === 'nuevo' ? (
          <PanelDetalle rotulo="Nuevo" titulo="Nuevo producto">
            <FormProducto key={`n${version}`} producto={null} categorias={categorias.data ?? []} alGuardar={(p) => fijar(p.id)} />
          </PanelDetalle>
        ) : modo ? (
          <DetalleProducto key={`${modo.id}-${version}`} producto={modo} categorias={categorias.data ?? []} />
        ) : null
      }
    />
  )
}

function DetalleProducto({ producto, categorias }: { producto: Producto; categorias: Categoria[] }) {
  const { puede } = useSesion()
  const editor = puede('carta.editar')
  const [pestana, setPestana] = useState<Pestana>(editor ? 'datos' : 'receta')
  const opciones: { valor: Pestana; texto: string }[] = [
    { valor: 'datos', texto: 'Datos' },
    { valor: 'receta', texto: 'Receta' },
    ...(editor ? [{ valor: 'precios' as const, texto: 'Precios' }] : []),
  ]
  return (
    <PanelDetalle
      rotulo="Producto"
      titulo={producto.nombre}
      subtitulo={`${pesos(producto.precio)} · ${TIPOS[producto.tipo].texto.toLowerCase()}`}
    >
      <div className="mb-5">
        <Pildoras etiqueta="Qué ver del producto" opciones={opciones} valor={pestana} alCambiar={setPestana} />
      </div>
      {pestana === 'datos' &&
        (editor ? (
          <FormProducto producto={producto} categorias={categorias} alGuardar={() => {}} />
        ) : (
          <DatosLectura producto={producto} categorias={categorias} />
        ))}
      {pestana === 'receta' && (
        <EditorReceta base={`/productos/${producto.id}`} editable={puede('recetas.editar')} />
      )}
      {pestana === 'precios' && <HistorialPrecios producto={producto} />}
    </PanelDetalle>
  )
}

/** Lo que ve quien no edita la carta (Producción): sin campos, ni el precio editable. */
function DatosLectura({ producto, categorias }: { producto: Producto; categorias: Categoria[] }) {
  const filas: [string, string][] = [
    ['Categoría', categorias.find((c) => c.id === producto.categoria_id)?.nombre ?? '—'],
    ['Tipo', TIPOS[producto.tipo].texto],
    ['Precio', pesos(producto.precio)],
    ['Estado', !producto.activo ? 'Inactivo' : producto.disponible ? 'Disponible' : 'Agotado'],
    ['Adiciones', producto.modificadores.map((m) => m.nombre).join(', ') || 'Ninguna'],
  ]
  return (
    <>
      <dl className="divide-y divide-linea">
        {filas.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 py-2.5">
            <dt className="text-cafe-medio">{k}</dt>
            <dd className="text-right font-semibold">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-sm text-cafe-suave">Los datos y el precio los cambia el administrador.</p>
    </>
  )
}

function FormProducto({
  producto,
  categorias,
  alGuardar,
}: {
  producto: Producto | null
  categorias: Categoria[]
  alGuardar: (p: Producto) => void
}) {
  const nuevo = producto === null
  const adiciones = useQuery({ queryKey: ['adiciones'], queryFn: () => api<Adicion[]>('/modificadores') })
  const [nombre, setNombre] = useState(producto?.nombre ?? '')
  const [categoriaElegida, setCategoriaId] = useState(producto?.categoria_id ?? '')
  // Las categorías pueden llegar después del primer render: sin elección, la primera.
  const categoriaId = categoriaElegida || categorias[0]?.id || ''
  const [tipo, setTipo] = useState<TipoProducto>(producto?.tipo ?? 'preparado')
  const [precio, setPrecio] = useState<number | null>(producto?.precio ?? null)
  const [disponible, setDisponible] = useState(producto?.disponible ?? true)
  const [activo, setActivo] = useState(producto?.activo ?? true)
  const [minimo, setMinimo] = useState(producto ? dec(producto.stock_minimo).toFixed() : '0')
  const [vida, setVida] = useState(producto?.dias_vida_util?.toString() ?? '')
  const [foto, setFoto] = useState(producto?.foto_url ?? null)
  const [mods, setMods] = useState<string[]>(producto?.modificadores.map((m) => m.id) ?? [])
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [guardado, setGuardado] = useState(false)
  const [subiendo, setSubiendo] = useState(false)
  const archivo = useRef<HTMLInputElement>(null)
  const vista = useImagen(foto)

  const guardar = useGuardar(
    (cuerpo: Record<string, unknown>) =>
      nuevo
        ? api<Producto>('/productos', { method: 'POST', json: cuerpo })
        : api<Producto>(`/productos/${producto.id}`, { method: 'PATCH', json: cuerpo }),
    [['productos'], ['inventario']],
    (p) => {
      setGuardado(true)
      alGuardar(p)
    },
  )

  async function subirFoto(f: File) {
    setSubiendo(true)
    try {
      const datos = new FormData()
      datos.append('archivo', f)
      const r = await api<{ url: string }>('/archivos', { method: 'POST', body: datos })
      setFoto(r.url)
    } catch {
      setErrores((e) => ({ ...e, foto: 'No pudimos subir la foto. Prueba con una imagen JPG o PNG de menos de 5 MB.' }))
    } finally {
      setSubiendo(false)
    }
  }

  function enviar(ev: FormEvent) {
    ev.preventDefault()
    const e: Record<string, string> = {}
    if (nombre.trim().length < 2) e.nombre = 'Escribe el nombre del producto (mínimo 2 letras).'
    if (!categoriaId) e.categoria = 'Elige la categoría.'
    if (precio === null) e.precio = 'Escribe el precio de venta.'
    const min = leerCantidad(minimo)
    if (tipo === 'lote' && min === null) e.minimo = 'Escribe el mínimo en unidades, por ejemplo 5.'
    if (vida && !/^\d{1,3}$/.test(vida)) e.vida = 'Escribe los días como número, por ejemplo 2.'
    setErrores(e)
    setGuardado(false)
    if (Object.keys(e).length) return
    guardar.mutate({
      nombre: nombre.trim(),
      categoria_id: categoriaId,
      tipo,
      precio,
      foto_url: foto,
      stock_minimo: tipo === 'lote' ? min : '0',
      dias_vida_util: tipo === 'lote' && vida ? Number(vida) : null,
      modificador_ids: mods,
      ...(nuevo ? {} : { disponible, activo }),
    })
  }

  return (
    <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <div className="grid size-20 shrink-0 place-items-center overflow-hidden rounded-tarjeta border border-dorado-claro bg-crema">
          {vista ? <img src={vista} alt={`Foto de ${nombre}`} className="size-full object-cover" /> : <ImagePlus aria-hidden className="size-7 text-cafe-suave" />}
        </div>
        <div>
          <input
            ref={archivo}
            type="file"
            accept="image/*"
            className="sr-only"
            tabIndex={-1}
            aria-hidden
            onChange={(e) => e.target.files?.[0] && subirFoto(e.target.files[0])}
          />
          <Boton variante="secundario" className="h-10 px-4 text-[15px]" disabled={subiendo} onClick={() => archivo.current?.click()}>
            {subiendo ? 'Subiendo…' : foto ? 'Cambiar foto' : 'Agregar foto'}
          </Boton>
          {foto && (
            <button type="button" onClick={() => setFoto(null)} className="ml-2 text-sm text-cafe-suave underline">
              Quitar
            </button>
          )}
          {errores.foto && <p className="mt-1.5 text-sm text-peligro-texto">{errores.foto}</p>}
        </div>
      </div>
      <Campo etiqueta="Nombre" value={nombre} maxLength={120} onChange={(e) => setNombre(e.target.value)} error={errores.nombre} />
      <div>
        <Selector etiqueta="Categoría" value={categoriaId} onChange={(e) => setCategoriaId(e.target.value)}>
          {categorias.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre}
            </option>
          ))}
        </Selector>
        {errores.categoria && <p className="mt-1.5 text-sm text-peligro-texto">{errores.categoria}</p>}
      </div>
      <fieldset>
        <legend className="mb-1.5 text-sm font-semibold">Tipo</legend>
        {(Object.keys(TIPOS) as TipoProducto[]).map((t) => (
          <label key={t} className="flex cursor-pointer items-start gap-3 py-1.5">
            <input
              type="radio"
              name="tipo"
              checked={tipo === t}
              onChange={() => setTipo(t)}
              className="mt-1 size-[18px] shrink-0 accent-fucsia"
            />
            <span>
              <span className="block text-[15px]">{TIPOS[t].texto}</span>
              <span className="block text-xs text-cafe-suave">{TIPOS[t].ayuda}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <CampoDinero etiqueta="Precio de venta" valor={precio} alCambiar={setPrecio} error={errores.precio} />
      {tipo === 'lote' && (
        <div className="grid grid-cols-2 gap-3">
          <Campo etiqueta="Mínimo en vitrina" inputMode="decimal" value={minimo} onChange={(e) => setMinimo(e.target.value)} error={errores.minimo} />
          <Campo etiqueta="Días de vida útil" inputMode="numeric" value={vida} onChange={(e) => setVida(e.target.value)} error={errores.vida} />
        </div>
      )}
      {(adiciones.data?.length ?? 0) > 0 && (
        <CasillasConBusqueda
          etiqueta="Adiciones que se le pueden poner"
          opciones={adiciones.data!.map((a) => ({ valor: a.id, texto: `${a.nombre} · ${pesos(a.precio)}` }))}
          marcadas={mods}
          alCambiar={setMods}
        />
      )}
      {!nuevo && (
        <>
          <Interruptor etiqueta="Disponible" ayuda="Si se agota, no aparece para vender." activo={disponible} alCambiar={setDisponible} />
          <Interruptor etiqueta="Activo" ayuda="Inactivo: sale de la carta pero conserva su historial." activo={activo} alCambiar={setActivo} />
        </>
      )}
      {guardar.error && <Aviso>{guardar.error}</Aviso>}
      {guardado && !guardar.error && <p role="status" className="text-sm font-semibold text-exito-texto">Cambios guardados.</p>}
      <PieFormulario>
        <Boton type="submit" disabled={guardar.isPending}>
          {guardar.isPending ? 'Guardando…' : nuevo ? 'Crear producto' : 'Guardar cambios'}
        </Boton>
      </PieFormulario>
    </form>
  )
}

function HistorialPrecios({ producto }: { producto: Producto }) {
  const precios = useQuery({
    queryKey: ['productos', 'precios', producto.id],
    queryFn: () => api<CambioPrecio[]>(`/productos/${producto.id}/precios`),
  })
  if (precios.isError) return <Aviso>No pudimos cargar el historial de precios.</Aviso>
  if (precios.isSuccess && precios.data.length === 0) return <Vacio>Todavía no hay cambios de precio.</Vacio>
  return (
    <ol aria-label="Historial de precios" className="flex flex-col divide-y divide-linea">
      {precios.data?.map((c) => {
        const fecha = new Date(c.fecha)
        return (
          <li key={c.fecha} className="py-2.5">
            <p className="font-semibold">
              {c.precio_anterior === null ? `Precio inicial ${pesos(c.precio_nuevo)}` : `${pesos(c.precio_anterior)} → ${pesos(c.precio_nuevo)}`}
            </p>
            <p className="text-sm text-cafe-suave">
              {fechaCorta(fecha)} · {hora(fecha)}
              {c.usuario ? ` · ${c.usuario}` : ''}
            </p>
          </li>
        )
      })}
    </ol>
  )
}
