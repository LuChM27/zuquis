import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useSesion } from '../../auth/contexto'
import { CasillasConBusqueda, FiltroLista } from '../../components/Buscador'
import { Aviso, Celda, FilaTabla, Interruptor, ListaDetalle, PanelDetalle, Tabla, Vacio } from '../../components/formulario'
import { Boton, Campo, Chip } from '../../components/ui'
import { api } from '../../lib/api'
import { coincide } from '../../lib/buscar'
import type { Insumo, Proveedor } from '../../lib/tipos'
import { useGuardar, useSeleccion, vacioANulo } from '../configuracion/acciones'
import { PieFormulario, TarjetaLista } from '../configuracion/comun'

export function Proveedores() {
  const { puede } = useSesion()
  const editor = puede('proveedores.gestionar')
  const proveedores = useQuery({
    queryKey: ['proveedores', 'todos'],
    queryFn: () => api<Proveedor[]>('/proveedores?incluir_inactivos=true'),
  })
  const { sel, version, elegir, fijar } = useSeleccion()
  const [busqueda, setBusqueda] = useState('')
  const todos = proveedores.data ?? []
  const lista = todos.filter((p) => coincide(`${p.nombre} ${p.insumos.map((i) => i.nombre).join(' ')}`, busqueda))
  const actual = sel === 'nuevo' ? null : (lista.find((p) => p.id === sel) ?? lista[0] ?? null)
  const modo = editor && (sel === 'nuevo' || (!actual && proveedores.isSuccess && todos.length === 0)) ? 'nuevo' : actual

  return (
    <ListaDetalle
      lista={
        <TarjetaLista titulo="Proveedores" nuevo={editor ? 'Nuevo proveedor' : undefined} alNuevo={() => elegir('nuevo')}>
          {todos.length > 0 && (
            <FiltroLista etiqueta="Buscar proveedor o insumo" valor={busqueda} alCambiar={setBusqueda} className="mb-4 max-w-sm" />
          )}
          {proveedores.isError && <Aviso>No pudimos cargar los proveedores. Recarga la página para intentarlo de nuevo.</Aviso>}
          {proveedores.isSuccess && lista.length === 0 && <Vacio>{todos.length ? 'Ningún proveedor coincide.' : 'Todavía no hay proveedores.'}</Vacio>}
          {lista.length > 0 && (
            <Tabla columnas={[{ texto: 'Proveedor' }, { texto: 'Suministra', ocultarMovil: true }, { texto: 'Estado' }]}>
              {lista.map((p) => (
                <FilaTabla key={p.id} seleccionada={modo !== 'nuevo' && actual?.id === p.id} alElegir={() => elegir(p.id)}>
                  <Celda>
                    <span className="block font-semibold">{p.nombre}</span>
                    {p.telefono && <span className="block text-sm text-cafe-suave">{p.telefono}</span>}
                  </Celda>
                  <Celda ocultarMovil className="text-cafe-medio">
                    {p.insumos.map((i) => i.nombre).join(', ') || '—'}
                  </Celda>
                  <Celda>{p.activo ? <Chip tono="exito">Activo</Chip> : <Chip>Inactivo</Chip>}</Celda>
                </FilaTabla>
              ))}
            </Tabla>
          )}
        </TarjetaLista>
      }
      detalle={
        modo ? (
          <PanelDetalle rotulo={modo === 'nuevo' ? 'Nuevo' : 'Proveedor'} titulo={modo === 'nuevo' ? 'Nuevo proveedor' : modo.nombre}>
            {editor ? (
              <FormProveedor key={version} proveedor={modo === 'nuevo' ? null : modo} alGuardar={(p) => fijar(p.id)} />
            ) : (
              <p className="text-cafe-medio">Suministra: {modo === 'nuevo' ? '' : modo.insumos.map((i) => i.nombre).join(', ') || 'sin insumos asignados'}.</p>
            )}
          </PanelDetalle>
        ) : null
      }
    />
  )
}

function FormProveedor({ proveedor, alGuardar }: { proveedor: Proveedor | null; alGuardar: (p: Proveedor) => void }) {
  const nuevo = proveedor === null
  const insumos = useQuery({ queryKey: ['insumos'], queryFn: () => api<Insumo[]>('/insumos') })
  const [nombre, setNombre] = useState(proveedor?.nombre ?? '')
  const [nit, setNit] = useState(proveedor?.nit_o_cedula ?? '')
  const [telefono, setTelefono] = useState(proveedor?.telefono ?? '')
  const [email, setEmail] = useState(proveedor?.email ?? '')
  const [activo, setActivo] = useState(proveedor?.activo ?? true)
  const [suministra, setSuministra] = useState<string[]>(proveedor?.insumos.map((i) => i.id) ?? [])
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [guardado, setGuardado] = useState(false)
  const guardar = useGuardar(
    (cuerpo: Record<string, unknown>) =>
      nuevo
        ? api<Proveedor>('/proveedores', { method: 'POST', json: cuerpo })
        : api<Proveedor>(`/proveedores/${proveedor.id}`, { method: 'PATCH', json: cuerpo }),
    [['proveedores']],
    (p) => {
      setGuardado(true)
      alGuardar(p)
    },
  )

  function enviar(ev: FormEvent) {
    ev.preventDefault()
    const e: Record<string, string> = {}
    if (nombre.trim().length < 2) e.nombre = 'Escribe el nombre del proveedor (mínimo 2 letras).'
    if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) e.email = 'Revisa el correo, por ejemplo ventas@proveedor.co.'
    setErrores(e)
    setGuardado(false)
    if (Object.keys(e).length) return
    guardar.mutate({
      nombre: nombre.trim(),
      nit_o_cedula: vacioANulo(nit),
      telefono: vacioANulo(telefono),
      email: vacioANulo(email),
      insumo_ids: suministra,
      ...(nuevo ? {} : { activo }),
    })
  }

  return (
    <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
      <Campo etiqueta="Nombre" value={nombre} maxLength={120} onChange={(e) => setNombre(e.target.value)} error={errores.nombre} />
      <Campo etiqueta="NIT o cédula (opcional)" value={nit} maxLength={30} onChange={(e) => setNit(e.target.value)} />
      <div className="grid grid-cols-2 gap-3">
        <Campo etiqueta="Teléfono" type="tel" value={telefono} maxLength={40} onChange={(e) => setTelefono(e.target.value)} />
        <Campo etiqueta="Correo" type="email" value={email} maxLength={200} onChange={(e) => setEmail(e.target.value)} error={errores.email} />
      </div>
      {(insumos.data?.length ?? 0) > 0 && (
        <CasillasConBusqueda
          etiqueta="Insumos que suministra"
          opciones={insumos.data!.map((i) => ({ valor: i.id, texto: i.nombre }))}
          marcadas={suministra}
          alCambiar={setSuministra}
        />
      )}
      {!nuevo && <Interruptor etiqueta="Activo" activo={activo} alCambiar={setActivo} />}
      {guardar.error && <Aviso>{guardar.error}</Aviso>}
      {guardado && !guardar.error && <p role="status" className="text-sm font-semibold text-exito-texto">Cambios guardados.</p>}
      <PieFormulario>
        <Boton type="submit" disabled={guardar.isPending}>
          {guardar.isPending ? 'Guardando…' : nuevo ? 'Crear proveedor' : 'Guardar cambios'}
        </Boton>
      </PieFormulario>
    </form>
  )
}
