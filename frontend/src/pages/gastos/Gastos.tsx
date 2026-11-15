import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Plus } from 'lucide-react'
import { useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { useSesion } from '../../auth/contexto'
import { Buscador } from '../../components/Buscador'
import { CampoDinero } from '../../components/CampoDinero'
import { Aviso, Celda, FilaTabla, ListaDetalle, PanelDetalle, Pildoras, Selector, Tabla, Vacio } from '../../components/formulario'
import { Boton, Campo, Chip, EncabezadoPagina, Tarjeta } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api } from '../../lib/api'
import { fechaCorta, pesos } from '../../lib/formato'
import type { CategoriaGasto, FuenteGasto, Gasto, MetodoPago, Pagina } from '../../lib/tipos'
import { hoyIso } from '../../lib/unidades'
import { useImagen } from '../carta/utilidades'
import { useCaja } from '../caja/usarCaja'
import { CategoriasGasto } from './CategoriasGasto'

const FUENTES: Record<FuenteGasto, { texto: string; ayuda: string }> = {
  caja: { texto: 'De la caja', ayuda: 'Sale del dinero de la caja abierta y aparece en el cierre.' },
  banco: { texto: 'Del banco', ayuda: 'Se pagó desde una cuenta del negocio; no toca la caja.' },
  duenos: { texto: 'De los dueños', ayuda: 'Lo pagó un dueño de su bolsillo; no toca la caja.' },
}
const TAMANO = 20

/** Gastos de caja, banco o dueños (RF-21 a RF-23) y sus categorías con cuenta PUC. */
export function Gastos() {
  const { puede } = useSesion()
  const [params, setParams] = useSearchParams()
  const categoriasVisibles = puede('config.editar')
  const seccion = categoriasVisibles && params.get('seccion') === 'categorias' ? 'categorias' : 'gastos'

  return (
    <>
      <EncabezadoPagina
        contexto="Lo que se paga para que el negocio funcione"
        titulo="Gastos"
        acciones={
          seccion === 'gastos' && (
            <Boton onClick={() => setParams({ gasto: 'nuevo' })}>
              <Plus aria-hidden className="size-5" />
              Registrar gasto
            </Boton>
          )
        }
      />
      {categoriasVisibles && (
        <div className="mb-5">
          <Pildoras
            etiqueta="Secciones de gastos"
            opciones={[
              { valor: 'gastos', texto: 'Gastos' },
              { valor: 'categorias', texto: 'Categorías' },
            ]}
            valor={seccion}
            alCambiar={(v) => setParams({ seccion: v })}
          />
        </div>
      )}
      {seccion === 'gastos' ? (
        <ListaGastos elegido={params.get('gasto') ?? undefined} alElegir={(id) => setParams(id ? { gasto: id } : {})} />
      ) : (
        <CategoriasGasto />
      )}
    </>
  )
}

function ListaGastos({ elegido, alElegir }: { elegido?: string; alElegir: (id: string | null) => void }) {
  const [fuente, setFuente] = useState<FuenteGasto | ''>('')
  const [categoria, setCategoria] = useState('')
  const [pagina, setPagina] = useState(1)
  const categorias = useCategorias()
  const filtros = `${fuente ? `&fuente=${fuente}` : ''}${categoria ? `&categoria_id=${categoria}` : ''}`
  const gastos = useQuery({
    queryKey: ['gastos', pagina, fuente, categoria],
    queryFn: () => api<Pagina<Gasto>>(`/gastos?page=${pagina}&size=${TAMANO}${filtros}`),
  })
  const paginas = Math.max(1, Math.ceil((gastos.data?.total ?? 0) / TAMANO))
  const actual = gastos.data?.items.find((g) => g.id === elegido)

  return (
    <ListaDetalle
      lista={
        <Tarjeta>
          <div className="grid gap-3">
            <Pildoras
              etiqueta="Fuente del gasto"
              opciones={[{ valor: '', texto: 'Todos' }, ...Object.entries(FUENTES).map(([v, f]) => ({ valor: v, texto: f.texto }))]}
              valor={fuente}
              alCambiar={(v) => {
                setFuente(v as FuenteGasto | '')
                setPagina(1)
              }}
            />
            <Buscador
              className="max-w-[360px]"
              etiqueta="Categoría"
              ocultarEtiqueta
              placeholder="Todas las categorías"
              opciones={[{ valor: '', texto: 'Todas las categorías' }, ...(categorias.data ?? []).map((c) => ({ valor: c.id, texto: c.nombre }))]}
              valor={categoria}
              alCambiar={(v) => {
                setCategoria(v)
                setPagina(1)
              }}
            />
          </div>
          <div className="mt-4">
            {gastos.isPending ? (
              <p className="text-cafe-medio">Cargando…</p>
            ) : gastos.data?.items.length === 0 ? (
              <Vacio>No hay gastos con esos filtros.</Vacio>
            ) : (
              <Tabla
                columnas={[
                  { texto: 'Fecha', ocultarMovil: true },
                  { texto: 'Gasto' },
                  { texto: 'Pagado', ocultarMovil: true },
                  { texto: 'Valor', derecha: true },
                ]}
              >
                {gastos.data?.items.map((g) => (
                  <FilaTabla key={g.id} seleccionada={g.id === elegido} alElegir={() => alElegir(g.id)}>
                    <Celda ocultarMovil className="whitespace-nowrap text-cafe-medio">
                      {fechaCorta(new Date(`${g.fecha}T12:00:00`))}
                    </Celda>
                    <Celda>
                      <span className="block font-medium">{g.descripcion}</span>
                      <span className="block text-sm text-cafe-suave">{g.categoria}</span>
                    </Celda>
                    <Celda ocultarMovil>
                      <span className="block">{FUENTES[g.fuente].texto}</span>
                      <span className="block text-sm text-cafe-suave">{g.metodo}</span>
                    </Celda>
                    <Celda derecha>
                      {g.estado === 'anulado' ? (
                        <Chip tono="neutro">Anulado</Chip>
                      ) : (
                        <span className="font-semibold whitespace-nowrap">{pesos(g.monto)}</span>
                      )}
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
          </div>
        </Tarjeta>
      }
      detalle={
        elegido === 'nuevo' ? (
          <FormGasto alRegistrar={(g) => alElegir(g.id)} />
        ) : actual ? (
          <DetalleGasto key={actual.id} gasto={actual} />
        ) : null
      }
    />
  )
}

function useCategorias() {
  return useQuery({ queryKey: ['categorias-gasto'], queryFn: () => api<CategoriaGasto[]>('/categorias-gasto') })
}

function FormGasto({ alRegistrar }: { alRegistrar: (g: Gasto) => void }) {
  const { puede } = useSesion()
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const caja = useCaja()
  const categorias = useCategorias()
  const metodos = useQuery({ queryKey: ['metodos-pago'], queryFn: () => api<MetodoPago[]>('/metodos-pago') })
  const soloCaja = !puede('gastos.crear')
  const [categoriaId, setCategoria] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [monto, setMonto] = useState<number | null>(null)
  const [fuente, setFuente] = useState<FuenteGasto>('caja')
  const [metodoElegido, setMetodo] = useState('')
  const [fecha, setFecha] = useState(hoyIso)
  const [soporte, setSoporte] = useState<string | null>(null)
  const [subiendo, setSubiendo] = useState(false)
  const [intento, setIntento] = useState(false)
  const clave = useRef(crypto.randomUUID())
  const archivo = useRef<HTMLInputElement>(null)

  const efectivo = metodos.data?.find((m) => m.es_efectivo)
  const metodoId = metodoElegido || (fuente === 'caja' ? efectivo?.id : metodos.data?.find((m) => !m.es_efectivo)?.id) || ''
  const errores = {
    categoria: !categoriaId ? 'Elige la categoría.' : undefined,
    descripcion: descripcion.trim().length < 3 ? 'Describe el gasto (mínimo 3 letras).' : undefined,
    monto: !monto ? 'Escribe el valor.' : undefined,
  }
  const cajaCerrada = fuente === 'caja' && caja.data && !caja.data.abierta

  const guardar = useMutation({
    mutationFn: () =>
      api<Gasto>('/gastos', {
        method: 'POST',
        idempotencia: clave.current,
        json: {
          categoria_id: categoriaId,
          descripcion: descripcion.trim(),
          monto,
          metodo_pago_id: metodoId,
          fuente,
          fecha: fuente === 'caja' ? null : fecha,
          soporte_url: soporte,
        },
      }),
    onSuccess: (g) => {
      avisar(`Gasto de ${pesos(g.monto)} registrado.`)
      void clienteQuery.invalidateQueries({ queryKey: ['gastos'] })
      void clienteQuery.invalidateQueries({ queryKey: ['caja'] })
      alRegistrar(g)
    },
    onError: (e) => avisar(e.message, 'error'),
  })

  async function subir(f: File) {
    setSubiendo(true)
    try {
      const datos = new FormData()
      datos.append('archivo', f)
      setSoporte((await api<{ url: string }>('/archivos', { method: 'POST', body: datos })).url)
    } catch {
      avisar('No pudimos subir la foto. Prueba con una imagen de menos de 5 MB.', 'error')
    } finally {
      setSubiendo(false)
    }
  }

  return (
    <PanelDetalle rotulo="Nuevo" titulo="Registrar gasto">
      <form
        noValidate
        className="grid gap-4"
        onSubmit={(e) => {
          e.preventDefault()
          setIntento(true)
          if (!errores.categoria && !errores.descripcion && !errores.monto && metodoId && !cajaCerrada) guardar.mutate()
        }}
      >
        <Buscador
          etiqueta="Categoría"
          opciones={(categorias.data ?? []).map((c) => ({ valor: c.id, texto: c.nombre, detalle: c.cuenta_puc ?? undefined }))}
          valor={categoriaId}
          alCambiar={setCategoria}
          error={intento ? errores.categoria : undefined}
        />
        <Campo
          etiqueta="Descripción"
          placeholder="Recibo de energía de octubre"
          value={descripcion}
          maxLength={200}
          onChange={(e) => setDescripcion(e.target.value)}
          error={intento ? errores.descripcion : undefined}
        />
        <CampoDinero etiqueta="Valor" valor={monto} alCambiar={setMonto} error={intento ? errores.monto : undefined} />
        {!soloCaja && (
          <fieldset>
            <legend className="mb-1.5 text-sm font-semibold">¿De dónde salió la plata?</legend>
            {(Object.keys(FUENTES) as FuenteGasto[]).map((f) => (
              <label key={f} className="flex cursor-pointer items-start gap-3 py-1.5">
                <input
                  type="radio"
                  name="fuente"
                  checked={fuente === f}
                  onChange={() => {
                    setFuente(f)
                    setMetodo('')
                  }}
                  className="mt-0.5 size-[18px] accent-fucsia"
                />
                <span>
                  <span className="block text-[15px] font-medium">{FUENTES[f].texto}</span>
                  <span className="block text-sm text-cafe-suave">{FUENTES[f].ayuda}</span>
                </span>
              </label>
            ))}
          </fieldset>
        )}
        <Selector etiqueta="Pagado con" value={metodoId} onChange={(e) => setMetodo(e.target.value)}>
          {metodos.data?.map((m) => (
            <option key={m.id} value={m.id}>
              {m.nombre}
            </option>
          ))}
        </Selector>
        {fuente !== 'caja' && <Campo etiqueta="Fecha" type="date" value={fecha} max={hoyIso()} onChange={(e) => setFecha(e.target.value)} />}
        <div>
          <p className="mb-1.5 text-sm font-semibold">Soporte (foto del recibo)</p>
          <input
            ref={archivo}
            type="file"
            accept="image/*"
            capture="environment"
            className="sr-only"
            tabIndex={-1}
            aria-hidden
            onChange={(e) => e.target.files?.[0] && void subir(e.target.files[0])}
          />
          <Boton variante="secundario" className="h-11 px-4 text-[15px]" disabled={subiendo} onClick={() => archivo.current?.click()}>
            <Camera aria-hidden className="size-[18px]" />
            {subiendo ? 'Subiendo…' : soporte ? 'Cambiar foto' : 'Tomar o subir foto'}
          </Boton>
          {soporte && <p className="mt-1.5 text-sm text-exito-texto">Foto adjunta.</p>}
        </div>
        {cajaCerrada && <Aviso>No hay caja abierta: un gasto de caja necesita la caja abierta.</Aviso>}
        <Boton type="submit" disabled={guardar.isPending || subiendo}>
          {guardar.isPending ? 'Registrando…' : 'Registrar gasto'}
        </Boton>
      </form>
    </PanelDetalle>
  )
}

function DetalleGasto({ gasto }: { gasto: Gasto }) {
  const { puede } = useSesion()
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const imagen = useImagen(gasto.soporte_url)
  const [motivo, setMotivo] = useState('')
  const [anulando, setAnulando] = useState(false)
  const anular = useMutation({
    mutationFn: () => api<Gasto>(`/gastos/${gasto.id}/anular`, { method: 'POST', json: { motivo: motivo.trim() } }),
    onSuccess: () => {
      avisar(gasto.fuente === 'caja' ? 'Gasto anulado: el dinero volvió a la caja abierta.' : 'Gasto anulado.')
      void clienteQuery.invalidateQueries({ queryKey: ['gastos'] })
      void clienteQuery.invalidateQueries({ queryKey: ['caja'] })
    },
    onError: (e) => avisar(e.message, 'error'),
  })
  const filas: [string, string][] = [
    ['Valor', pesos(gasto.monto)],
    ['Categoría', `${gasto.categoria ?? '—'}${gasto.cuenta_puc ? ` · PUC ${gasto.cuenta_puc}` : ''}`],
    ['Fecha', fechaCorta(new Date(`${gasto.fecha}T12:00:00`))],
    ['Pagado', `${FUENTES[gasto.fuente].texto} · ${gasto.metodo ?? ''}`],
    ['Registró', gasto.usuario ?? '—'],
  ]
  return (
    <PanelDetalle rotulo={gasto.estado === 'anulado' ? 'Gasto anulado' : 'Gasto'} titulo={gasto.descripcion}>
      <dl className="grid gap-2.5">
        {filas.map(([t, v]) => (
          <div key={t} className="flex items-baseline justify-between gap-3">
            <dt className="text-cafe-medio">{t}</dt>
            <dd className="text-right font-medium">{v}</dd>
          </div>
        ))}
      </dl>
      {gasto.estado === 'anulado' && gasto.motivo_anulacion && (
        <p className="mt-4 rounded-control bg-crema p-3 text-[15px]">
          <span className="font-semibold">Motivo de la anulación:</span> {gasto.motivo_anulacion}
        </p>
      )}
      {imagen && <img src={imagen} alt="Soporte del gasto" className="mt-4 max-h-[50dvh] w-full rounded-control object-contain" />}
      {gasto.estado === 'registrado' && puede('gastos.anular') && (
        <div className="mt-5">
          {anulando ? (
            <form
              className="grid gap-3"
              onSubmit={(e) => {
                e.preventDefault()
                if (motivo.trim().length >= 3) anular.mutate()
              }}
            >
              <Campo etiqueta="Motivo de la anulación" value={motivo} maxLength={200} onChange={(e) => setMotivo(e.target.value)} autoFocus />
              <div className="flex gap-3">
                <Boton variante="secundario" onClick={() => setAnulando(false)}>
                  Volver
                </Boton>
                <Boton type="submit" variante="peligro" disabled={motivo.trim().length < 3 || anular.isPending}>
                  Anular gasto
                </Boton>
              </div>
            </form>
          ) : (
            <Boton variante="peligro" className="w-full" onClick={() => setAnulando(true)}>
              Anular gasto
            </Boton>
          )}
        </div>
      )}
    </PanelDetalle>
  )
}
