import { useQuery } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'
import { AreaTexto, Aviso, Casilla, Celda, FilaTabla, Interruptor, ListaDetalle, PanelDetalle, Tabla } from '../../components/formulario'
import { Boton, Campo, Chip } from '../../components/ui'
import { api } from '../../lib/api'
import { MODULOS, type Permiso, type Rol } from '../../lib/tipos'
import { useGuardar, vacioANulo, useSeleccion } from './acciones'
import { PieFormulario, TarjetaLista } from './comun'

export function Roles() {
  const roles = useQuery({ queryKey: ['roles'], queryFn: () => api<Rol[]>('/roles') })
  const permisos = useQuery({ queryKey: ['permisos'], queryFn: () => api<Permiso[]>('/permisos'), staleTime: Infinity })
  const { sel, version, elegir, fijar } = useSeleccion()

  const lista = roles.data ?? []
  const actual = sel === 'nuevo' ? null : (lista.find((r) => r.id === sel) ?? lista[0] ?? null)
  const modo = sel === 'nuevo' || (!actual && roles.isSuccess) ? 'nuevo' : actual

  return (
    <ListaDetalle
      lista={
        <TarjetaLista titulo="Roles" nuevo="Nuevo rol" alNuevo={() => elegir('nuevo')}>
          {roles.isError ? (
            <Aviso>No pudimos cargar los roles. Recarga la página para intentarlo de nuevo.</Aviso>
          ) : (
            <Tabla columnas={[{ texto: 'Rol' }, { texto: 'Permisos', derecha: true, ocultarMovil: true }, { texto: 'Usuarios', derecha: true }, { texto: 'Estado' }]}>
              {lista.map((r) => (
                <FilaTabla key={r.id} seleccionada={modo !== 'nuevo' && actual?.id === r.id} alElegir={() => elegir(r.id)}>
                  <Celda>
                    <p className="font-semibold">{r.nombre}</p>
                    {r.descripcion && <p className="text-sm text-cafe-suave">{r.descripcion}</p>}
                  </Celda>
                  <Celda derecha ocultarMovil className="text-cafe-medio">{r.permisos.length}</Celda>
                  <Celda derecha className="text-cafe-medio">{r.usuarios}</Celda>
                  <Celda>{r.activo ? <Chip tono="exito">Activo</Chip> : <Chip>Inactivo</Chip>}</Celda>
                </FilaTabla>
              ))}
            </Tabla>
          )}
        </TarjetaLista>
      }
      detalle={
        permisos.data && modo ? (
          <FormRol
            key={version}
            rol={modo === 'nuevo' ? null : modo}
            permisos={permisos.data}
            alGuardar={(r) => fijar(r?.id ?? null)}
            alDuplicar={(r) => elegir(r.id)}
          />
        ) : null
      }
    />
  )
}

function FormRol({
  rol,
  permisos,
  alGuardar,
  alDuplicar,
}: {
  rol: Rol | null
  permisos: Permiso[]
  alGuardar: (r: Rol | null) => void
  alDuplicar: (r: Rol) => void
}) {
  const nuevo = rol === null
  const [nombre, setNombre] = useState(rol?.nombre ?? '')
  const [descripcion, setDescripcion] = useState(rol?.descripcion ?? '')
  const [activo, setActivo] = useState(rol?.activo ?? true)
  const [marcados, setMarcados] = useState(() => new Set(rol?.permisos ?? []))
  const [errorNombre, setErrorNombre] = useState<string>()
  const [confirmarEliminar, setConfirmarEliminar] = useState(false)
  const [guardado, setGuardado] = useState(false)

  const porModulo = useMemo(() => {
    const m = new Map<string, Permiso[]>()
    for (const p of permisos) m.set(p.modulo, [...(m.get(p.modulo) ?? []), p])
    return [...m.entries()]
  }, [permisos])

  const guardar = useGuardar(
    (cuerpo: Record<string, unknown>) =>
      nuevo
        ? api<Rol>('/roles', { method: 'POST', json: cuerpo })
        : api<Rol>(`/roles/${rol.id}`, { method: 'PATCH', json: cuerpo }),
    [['roles'], ['usuarios']],
    (r) => {
      setGuardado(true)
      alGuardar(r)
    },
  )
  const duplicar = useGuardar(() => api<Rol>(`/roles/${rol!.id}/duplicar`, { method: 'POST' }), [['roles']], alDuplicar)
  const eliminar = useGuardar(() => api<void>(`/roles/${rol!.id}`, { method: 'DELETE' }), [['roles']], () => alGuardar(null))

  function enviar(e: FormEvent) {
    e.preventDefault()
    if (nombre.trim().length < 2) {
      setErrorNombre('Escribe el nombre del rol (mínimo 2 letras).')
      return
    }
    setErrorNombre(undefined)
    setGuardado(false)
    const cuerpo: Record<string, unknown> = {
      nombre: nombre.trim(),
      descripcion: vacioANulo(descripcion),
      permisos: [...marcados],
    }
    if (!nuevo) cuerpo.activo = activo
    guardar.mutate(cuerpo)
  }

  const alternar = (clave: string, v: boolean) =>
    setMarcados((prev) => {
      const s = new Set(prev)
      if (v) s.add(clave)
      else s.delete(clave)
      return s
    })

  const error = guardar.error ?? duplicar.error ?? eliminar.error

  return (
    <PanelDetalle
      rotulo={nuevo ? 'Nuevo rol' : rol.es_base ? 'Rol base' : 'Rol'}
      titulo={nuevo ? 'Crear un rol' : rol.nombre}
      subtitulo={
        nuevo
          ? 'Elige qué puede hacer quien tenga este rol.'
          : `${rol.usuarios} ${rol.usuarios === 1 ? 'usuario' : 'usuarios'} · ${marcados.size} permisos`
      }
    >
      <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
        <Campo etiqueta="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} error={errorNombre} />
        <AreaTexto etiqueta="Descripción" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} maxLength={200} />

        <fieldset>
          <legend className="text-sm font-semibold">Permisos</legend>
          <div className="mt-1 divide-y divide-linea">
            {porModulo.map(([modulo, lista]) => (
              <div key={modulo} className="py-2.5">
                <p className="text-[13px] font-semibold tracking-[0.08em] text-cafe-suave uppercase">{MODULOS[modulo] ?? modulo}</p>
                {lista.map((p) => (
                  <Casilla key={p.clave} etiqueta={p.descripcion} marcada={marcados.has(p.clave)} alCambiar={(v) => alternar(p.clave, v)} />
                ))}
              </div>
            ))}
          </div>
        </fieldset>

        {!nuevo && (
          <Interruptor
            etiqueta="Rol activo"
            ayuda={rol.es_base && rol.usuarios > 0 ? 'Un rol base con usuarios no se puede desactivar.' : 'Si lo desactivas, quienes lo tengan pierden estos permisos.'}
            activo={activo}
            alCambiar={setActivo}
            deshabilitado={rol.es_base && rol.usuarios > 0}
          />
        )}

        {error && <Aviso>{error}</Aviso>}

        <PieFormulario>
          <Boton type="submit" disabled={guardar.isPending} className="w-full">
            {guardar.isPending ? 'Guardando…' : nuevo ? 'Crear rol' : 'Guardar cambios'}
          </Boton>
          <p role="status" className="min-h-5 text-center text-sm font-semibold text-exito-texto">
            {guardado && 'Cambios guardados'}
          </p>
          {!nuevo && (
            <Boton variante="secundario" onClick={() => duplicar.mutate(undefined)} disabled={duplicar.isPending} className="w-full">
              Duplicar como rol nuevo
            </Boton>
          )}
          {!nuevo && !rol.es_base && rol.usuarios === 0 &&
            (confirmarEliminar ? (
              <div className="rounded-control bg-peligro-fondo p-3.5">
                <p className="text-sm text-peligro-texto">
                  Se eliminará el rol «{rol.nombre}». Esta acción no se puede deshacer.
                </p>
                <div className="mt-3 flex gap-2">
                  <Boton variante="peligro" onClick={() => eliminar.mutate(undefined)} disabled={eliminar.isPending} className="h-11 flex-1">
                    Eliminar «{rol.nombre}»
                  </Boton>
                  <Boton variante="secundario" onClick={() => setConfirmarEliminar(false)} className="h-11">
                    Cancelar
                  </Boton>
                </div>
              </div>
            ) : (
              <Boton variante="peligro" onClick={() => setConfirmarEliminar(true)} className="w-full">
                Eliminar rol
              </Boton>
            ))}
        </PieFormulario>
      </form>
    </PanelDetalle>
  )
}
