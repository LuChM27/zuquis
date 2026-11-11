import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Aviso, Celda, FilaTabla, Interruptor, ListaDetalle, PanelDetalle, Selector, Tabla } from '../../components/formulario'
import { Boton, Campo, Chip } from '../../components/ui'
import { api } from '../../lib/api'
import type { MetodoPago, Titular } from '../../lib/tipos'
import { useGuardar, vacioANulo, useSeleccion } from './acciones'
import { PieFormulario, TarjetaLista } from './comun'

const TITULARES: Record<Titular, string> = { negocio: 'Cuenta del negocio', dueno: 'Cuenta personal del dueño' }

export function MetodosPago() {
  const metodos = useQuery({
    queryKey: ['metodos-pago', 'todos'],
    queryFn: () => api<MetodoPago[]>('/metodos-pago?solo_activos=false'),
  })
  const { sel, version, elegir, fijar } = useSeleccion()
  const lista = metodos.data ?? []
  const actual = sel === 'nuevo' ? null : (lista.find((m) => m.id === sel) ?? lista[0] ?? null)
  const modo = sel === 'nuevo' || (!actual && metodos.isSuccess) ? 'nuevo' : actual

  return (
    <ListaDetalle
      lista={
        <TarjetaLista titulo="Métodos de pago" nuevo="Nuevo método" alNuevo={() => elegir('nuevo')}>
          {metodos.isError ? (
            <Aviso>No pudimos cargar los métodos de pago. Recarga la página para intentarlo de nuevo.</Aviso>
          ) : (
            <Tabla columnas={[{ texto: 'Método' }, { texto: 'Titular', ocultarMovil: true }, { texto: 'Cuenta PUC', ocultarMovil: true }, { texto: 'Estado' }]}>
              {lista.map((m) => (
                <FilaTabla key={m.id} seleccionada={modo !== 'nuevo' && actual?.id === m.id} alElegir={() => elegir(m.id)}>
                  <Celda>
                    <p className="font-semibold">{m.nombre}</p>
                    {m.es_efectivo && <p className="text-sm text-cafe-suave">Efectivo · se cuenta en el arqueo</p>}
                  </Celda>
                  <Celda ocultarMovil className="text-cafe-medio">{m.titular === 'dueno' ? 'Dueño' : 'Negocio'}</Celda>
                  <Celda ocultarMovil className="text-cafe-medio">{m.cuenta_puc ?? '—'}</Celda>
                  <Celda>{m.activo ? <Chip tono="exito">Activo</Chip> : <Chip>Inactivo</Chip>}</Celda>
                </FilaTabla>
              ))}
            </Tabla>
          )}
        </TarjetaLista>
      }
      detalle={
        modo ? (
          <FormMetodo key={version} metodo={modo === 'nuevo' ? null : modo} alGuardar={(m) => fijar(m.id)} />
        ) : null
      }
    />
  )
}

function FormMetodo({ metodo, alGuardar }: { metodo: MetodoPago | null; alGuardar: (m: MetodoPago) => void }) {
  const nuevo = metodo === null
  const [nombre, setNombre] = useState(metodo?.nombre ?? '')
  const [titular, setTitular] = useState<Titular>(metodo?.titular ?? 'negocio')
  const [puc, setPuc] = useState(metodo?.cuenta_puc ?? '')
  const [orden, setOrden] = useState(String(metodo?.orden ?? 0))
  const [activo, setActivo] = useState(metodo?.activo ?? true)
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [guardado, setGuardado] = useState(false)

  const guardar = useGuardar(
    (cuerpo: Record<string, unknown>) =>
      nuevo
        ? api<MetodoPago>('/metodos-pago', { method: 'POST', json: cuerpo })
        : api<MetodoPago>(`/metodos-pago/${metodo.id}`, { method: 'PATCH', json: cuerpo }),
    [['metodos-pago']],
    (m) => {
      setGuardado(true)
      alGuardar(m)
    },
  )

  function enviar(ev: FormEvent) {
    ev.preventDefault()
    const e: Record<string, string> = {}
    if (nombre.trim().length < 2) e.nombre = 'Escribe el nombre del método (mínimo 2 letras).'
    if (puc && !/^\d{1,10}$/.test(puc)) e.puc = 'La cuenta PUC lleva solo números, como 1110.'
    if (!/^\d+$/.test(orden)) e.orden = 'Escribe un número entero.'
    setErrores(e)
    if (Object.keys(e).length) return
    setGuardado(false)
    const cuerpo: Record<string, unknown> = { nombre: nombre.trim(), titular, cuenta_puc: vacioANulo(puc), orden: Number(orden) }
    if (!nuevo) cuerpo.activo = activo
    guardar.mutate(cuerpo)
  }

  return (
    <PanelDetalle
      rotulo={nuevo ? 'Nuevo método' : 'Método de pago'}
      titulo={nuevo ? 'Agregar método de pago' : metodo.nombre}
      subtitulo={nuevo ? 'Aparecerá en el cobro y en el arqueo de caja.' : metodo.es_efectivo ? 'Efectivo: es el único que se cuenta billete a billete en el cierre.' : 'Se compara con lo que muestra la app del banco en el cierre.'}
    >
      <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
        <Campo etiqueta="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} error={errores.nombre} placeholder="Ej.: Daviplata" />
        <Selector etiqueta="¿A qué cuenta llega el dinero?" value={titular} onChange={(e) => setTitular(e.target.value as Titular)}>
          {Object.entries(TITULARES).map(([v, t]) => (
            <option key={v} value={v}>{t}</option>
          ))}
        </Selector>
        <div className="grid grid-cols-2 gap-3">
          <Campo etiqueta="Cuenta PUC" inputMode="numeric" value={puc} onChange={(e) => setPuc(e.target.value.trim())} error={errores.puc} placeholder="1110" />
          <Campo etiqueta="Orden en el cobro" inputMode="numeric" value={orden} onChange={(e) => setOrden(e.target.value.trim())} error={errores.orden} />
        </div>
        {!nuevo && (
          <Interruptor etiqueta="Disponible para cobrar" ayuda="Si lo desactivas, deja de aparecer en el cobro; el historial se conserva." activo={activo} alCambiar={setActivo} />
        )}
        {guardar.error && <Aviso>{guardar.error}</Aviso>}
        <PieFormulario>
          <Boton type="submit" disabled={guardar.isPending} className="w-full">
            {guardar.isPending ? 'Guardando…' : nuevo ? 'Crear método' : 'Guardar cambios'}
          </Boton>
          <p role="status" className="min-h-5 text-center text-sm font-semibold text-exito-texto">
            {guardado && 'Cambios guardados'}
          </p>
        </PieFormulario>
      </form>
    </PanelDetalle>
  )
}
