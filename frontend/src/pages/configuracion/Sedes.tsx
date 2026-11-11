import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useYo } from '../../auth/contexto'
import { Aviso, Celda, FilaTabla, Interruptor, ListaDetalle, PanelDetalle, Tabla } from '../../components/formulario'
import { Boton, Campo, Chip } from '../../components/ui'
import { api } from '../../lib/api'
import type { Sede } from '../../lib/tipos'
import { useGuardar, vacioANulo, useSeleccion } from './acciones'
import { PieFormulario, TarjetaLista } from './comun'

export function Sedes() {
  const sedes = useQuery({ queryKey: ['sedes'], queryFn: () => api<Sede[]>('/sedes') })
  const { sel, version, elegir, fijar } = useSeleccion()
  const lista = sedes.data ?? []
  const actual = sel === 'nuevo' ? null : (lista.find((s) => s.id === sel) ?? lista[0] ?? null)
  const modo = sel === 'nuevo' || (!actual && sedes.isSuccess) ? 'nuevo' : actual

  return (
    <ListaDetalle
      lista={
        <TarjetaLista titulo="Sedes" nuevo="Nueva sede" alNuevo={() => elegir('nuevo')}>
          {sedes.isError ? (
            <Aviso>No pudimos cargar las sedes. Recarga la página para intentarlo de nuevo.</Aviso>
          ) : (
            <Tabla columnas={[{ texto: 'Sede' }, { texto: 'Teléfono', ocultarMovil: true }, { texto: 'Estado' }]}>
              {lista.map((s) => (
                <FilaTabla key={s.id} seleccionada={modo !== 'nuevo' && actual?.id === s.id} alElegir={() => elegir(s.id)}>
                  <Celda>
                    <p className="font-semibold">{s.nombre}</p>
                    {s.direccion && <p className="text-sm text-cafe-suave">{s.direccion}</p>}
                  </Celda>
                  <Celda ocultarMovil className="text-cafe-medio">{s.telefono ?? '—'}</Celda>
                  <Celda>{s.activa ? <Chip tono="exito">Activa</Chip> : <Chip>Inactiva</Chip>}</Celda>
                </FilaTabla>
              ))}
            </Tabla>
          )}
        </TarjetaLista>
      }
      detalle={modo ? <FormSede key={version} sede={modo === 'nuevo' ? null : modo} alGuardar={(s) => fijar(s.id)} /> : null}
    />
  )
}

function FormSede({ sede, alGuardar }: { sede: Sede | null; alGuardar: (s: Sede) => void }) {
  const yo = useYo()
  const nuevo = sede === null
  const [nombre, setNombre] = useState(sede?.nombre ?? '')
  const [direccion, setDireccion] = useState(sede?.direccion ?? '')
  const [telefono, setTelefono] = useState(sede?.telefono ?? '')
  const [activa, setActiva] = useState(sede?.activa ?? true)
  const [errorNombre, setErrorNombre] = useState<string>()
  const [guardado, setGuardado] = useState(false)

  const guardar = useGuardar(
    (cuerpo: Record<string, unknown>) =>
      nuevo
        ? api<Sede>('/sedes', { method: 'POST', json: cuerpo })
        : api<Sede>(`/sedes/${sede.id}`, { method: 'PATCH', json: cuerpo }),
    [['sedes']],
    (s) => {
      setGuardado(true)
      alGuardar(s)
    },
  )

  function enviar(e: FormEvent) {
    e.preventDefault()
    if (nombre.trim().length < 2) {
      setErrorNombre('Escribe el nombre de la sede (mínimo 2 letras).')
      return
    }
    setErrorNombre(undefined)
    setGuardado(false)
    const cuerpo: Record<string, unknown> = { nombre: nombre.trim(), direccion: vacioANulo(direccion), telefono: vacioANulo(telefono) }
    if (!nuevo) cuerpo.activa = activa
    guardar.mutate(cuerpo)
  }

  const esActual = sede?.id === yo.sede.id

  return (
    <PanelDetalle rotulo={nuevo ? 'Nueva sede' : 'Sede'} titulo={nuevo ? 'Agregar una sede' : sede.nombre} subtitulo={nuevo ? 'Cada sede lleva su propia caja, inventario y consecutivos.' : undefined}>
      <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
        <Campo etiqueta="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} error={errorNombre} />
        <Campo etiqueta="Dirección" value={direccion} onChange={(e) => setDireccion(e.target.value)} />
        <Campo etiqueta="Teléfono" type="tel" inputMode="tel" value={telefono} onChange={(e) => setTelefono(e.target.value)} />
        {!nuevo && (
          <Interruptor
            etiqueta="Sede activa"
            ayuda={esActual ? 'Es la sede de tu sesión actual; no se puede desactivar desde aquí.' : undefined}
            activo={activa}
            alCambiar={setActiva}
            deshabilitado={esActual}
          />
        )}
        {guardar.error && <Aviso>{guardar.error}</Aviso>}
        <PieFormulario>
          <Boton type="submit" disabled={guardar.isPending} className="w-full">
            {guardar.isPending ? 'Guardando…' : nuevo ? 'Crear sede' : 'Guardar cambios'}
          </Boton>
          <p role="status" className="min-h-5 text-center text-sm font-semibold text-exito-texto">
            {guardado && 'Cambios guardados'}
          </p>
        </PieFormulario>
      </form>
    </PanelDetalle>
  )
}
