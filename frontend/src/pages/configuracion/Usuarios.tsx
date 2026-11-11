import { useQuery } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'
import { useYo } from '../../auth/contexto'
import { Aviso, Casilla, Celda, FilaTabla, Interruptor, ListaDetalle, PanelDetalle, Tabla, Vacio } from '../../components/formulario'
import { Boton, Campo, Chip } from '../../components/ui'
import { api } from '../../lib/api'
import { fechaCorta, hora } from '../../lib/formato'
import type { Asignacion, Rol, Sede, Usuario } from '../../lib/tipos'
import { useGuardar, useSeleccion } from './acciones'
import { PieFormulario, TarjetaLista } from './comun'

export function Usuarios() {
  const usuarios = useQuery({ queryKey: ['usuarios'], queryFn: () => api<Usuario[]>('/usuarios') })
  const roles = useQuery({ queryKey: ['roles'], queryFn: () => api<Rol[]>('/roles') })
  const sedes = useQuery({ queryKey: ['sedes'], queryFn: () => api<Sede[]>('/sedes') })
  const { sel, version, elegir, fijar } = useSeleccion()

  const lista = usuarios.data ?? []
  const actual = sel === 'nuevo' ? null : (lista.find((u) => u.id === sel) ?? lista[0] ?? null)
  const modo = sel === 'nuevo' || (!actual && usuarios.isSuccess) ? 'nuevo' : actual

  return (
    <ListaDetalle
      lista={
        <TarjetaLista titulo="Usuarios" nuevo="Nuevo usuario" alNuevo={() => elegir('nuevo')}>
          {usuarios.isError ? (
            <Aviso>No pudimos cargar los usuarios. Recarga la página para intentarlo de nuevo.</Aviso>
          ) : (
            <Tabla columnas={[{ texto: 'Usuario' }, { texto: 'Rol' , ocultarMovil: true }, { texto: 'Último acceso', ocultarMovil: true }, { texto: 'Estado' }]}>
              {lista.map((u) => (
                <FilaTabla key={u.id} seleccionada={modo !== 'nuevo' && actual?.id === u.id} alElegir={() => elegir(u.id)}>
                  <Celda>
                    <p className="font-semibold">{u.nombre}</p>
                    <p className="text-sm text-cafe-suave">{u.email}</p>
                  </Celda>
                  <Celda ocultarMovil className="text-cafe-medio">
                    {[...new Set(u.roles.map((r) => r.rol_nombre))].join(', ')}
                  </Celda>
                  <Celda ocultarMovil className="whitespace-nowrap text-cafe-medio">
                    {u.ultimo_acceso ? `${fechaCorta(new Date(u.ultimo_acceso))} · ${hora(new Date(u.ultimo_acceso))}` : 'Nunca'}
                  </Celda>
                  <Celda>
                    <EstadoUsuario u={u} />
                  </Celda>
                </FilaTabla>
              ))}
            </Tabla>
          )}
          {usuarios.isSuccess && lista.length === 0 && <Vacio>Aún no hay usuarios.</Vacio>}
        </TarjetaLista>
      }
      detalle={
        roles.data && sedes.data && modo ? (
          <FormUsuario
            key={version}
            usuario={modo === 'nuevo' ? null : modo}
            roles={roles.data.filter((r) => r.activo)}
            sedes={sedes.data.filter((s) => s.activa)}
            alGuardar={(u) => fijar(u.id)}
          />
        ) : null
      }
    />
  )
}

function EstadoUsuario({ u }: { u: Usuario }) {
  if (u.bloqueado) return <Chip tono="peligro">Bloqueado</Chip>
  if (!u.activo) return <Chip tono="neutro">Inactivo</Chip>
  return <Chip tono="exito">Activo</Chip>
}

const claveAsig = (a: Asignacion) => `${a.rol_id}|${a.sede_id}`

function FormUsuario({
  usuario,
  roles,
  sedes,
  alGuardar,
}: {
  usuario: Usuario | null
  roles: Rol[]
  sedes: Sede[]
  alGuardar: (u: Usuario) => void
}) {
  const yo = useYo()
  const nuevo = usuario === null
  const [nombre, setNombre] = useState(usuario?.nombre ?? '')
  const [email, setEmail] = useState(usuario?.email ?? '')
  const [clave, setClave] = useState('')
  const [activo, setActivo] = useState(usuario?.activo ?? true)
  const [asignaciones, setAsignaciones] = useState<Set<string>>(
    () => new Set((usuario?.roles ?? []).map(claveAsig)),
  )
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [guardado, setGuardado] = useState(false)

  useEffect(() => {
    if (!guardado) return
    const t = setTimeout(() => setGuardado(false), 3000)
    return () => clearTimeout(t)
  }, [guardado])

  const guardar = useGuardar(
    (cuerpo: Record<string, unknown>) =>
      nuevo
        ? api<Usuario>('/usuarios', { method: 'POST', json: cuerpo })
        : api<Usuario>(`/usuarios/${usuario.id}`, { method: 'PATCH', json: cuerpo }),
    [['usuarios'], ['roles']],
    (u) => {
      setGuardado(true)
      setClave('')
      alGuardar(u)
    },
  )

  function validar(): Record<string, string> {
    const e: Record<string, string> = {}
    if (nombre.trim().length < 2) e.nombre = 'Escribe el nombre (mínimo 2 letras).'
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) e.email = 'Escribe un correo como nombre@correo.com.'
    if ((nuevo || clave) && clave.length < 8) e.clave = 'La contraseña necesita al menos 8 caracteres.'
    if (asignaciones.size === 0) e.roles = 'Asigna al menos un rol.'
    return e
  }

  function enviar(ev: FormEvent) {
    ev.preventDefault()
    const e = validar()
    setErrores(e)
    if (Object.keys(e).length) return
    const roles = [...asignaciones].map((k) => {
      const [rol_id, sede_id] = k.split('|')
      return { rol_id, sede_id }
    })
    const cuerpo: Record<string, unknown> = { nombre: nombre.trim(), email: email.trim(), roles }
    if (clave) cuerpo.password = clave
    if (!nuevo) cuerpo.activo = activo
    guardar.mutate(cuerpo)
  }

  const alternar = (k: string, v: boolean) =>
    setAsignaciones((prev) => {
      const s = new Set(prev)
      if (v) s.add(k)
      else s.delete(k)
      return s
    })

  const esYo = usuario?.id === yo.usuario.id

  return (
    <PanelDetalle
      rotulo={nuevo ? 'Nuevo usuario' : 'Usuario'}
      titulo={nuevo ? 'Agregar a alguien del equipo' : usuario.nombre}
      subtitulo={nuevo ? 'Entrará con su correo y la contraseña que definas aquí.' : usuario.email}
    >
      <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
        <Campo etiqueta="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} error={errores.nombre} autoComplete="off" />
        <Campo etiqueta="Correo" type="email" value={email} onChange={(e) => setEmail(e.target.value)} error={errores.email} autoComplete="off" />
        <Campo
          etiqueta={nuevo ? 'Contraseña' : 'Nueva contraseña (opcional)'}
          type="password"
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          error={errores.clave}
          autoComplete="new-password"
          placeholder={nuevo ? 'Mínimo 8 caracteres' : 'Déjala vacía para no cambiarla'}
        />

        <fieldset>
          <legend className="mb-1 text-sm font-semibold">Rol{sedes.length > 1 ? ' por sede' : ''}</legend>
          {sedes.map((s) => (
            <div key={s.id} className={sedes.length > 1 ? 'mt-2' : ''}>
              {sedes.length > 1 && <p className="text-sm text-cafe-suave">{s.nombre}</p>}
              {roles.map((r) => {
                const k = claveAsig({ rol_id: r.id, sede_id: s.id })
                return (
                  <Casilla key={k} etiqueta={r.nombre} ayuda={r.descripcion ?? undefined} marcada={asignaciones.has(k)} alCambiar={(v) => alternar(k, v)} />
                )
              })}
            </div>
          ))}
          {errores.roles && <p className="mt-1 text-sm text-peligro-texto">{errores.roles}</p>}
        </fieldset>

        {!nuevo && (
          <Interruptor
            etiqueta="Puede entrar al sistema"
            ayuda={esYo ? 'No puedes desactivar tu propio usuario.' : 'Si lo desactivas, se cierra su acceso pero se conserva su historial.'}
            activo={activo}
            alCambiar={setActivo}
            deshabilitado={esYo}
          />
        )}

        {usuario?.bloqueado && (
          <Aviso tono="aviso">
            Está bloqueado por intentos fallidos de contraseña.{' '}
            <button
              type="button"
              className="font-semibold text-fucsia underline underline-offset-2"
              onClick={() => guardar.mutate({ desbloquear: true })}
            >
              Desbloquear ahora
            </button>
          </Aviso>
        )}

        {guardar.error && <Aviso>{guardar.error}</Aviso>}

        <PieFormulario>
          <Boton type="submit" disabled={guardar.isPending} className="w-full">
            {guardar.isPending ? 'Guardando…' : nuevo ? 'Crear usuario' : 'Guardar cambios'}
          </Boton>
          <p role="status" className="min-h-5 text-center text-sm font-semibold text-exito-texto">
            {guardado && 'Cambios guardados'}
          </p>
        </PieFormulario>
      </form>
    </PanelDetalle>
  )
}
