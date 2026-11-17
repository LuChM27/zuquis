import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Buscador } from '../../components/Buscador'
import { Dialogo } from '../../components/Dialogo'
import { Aviso } from '../../components/formulario'
import { Boton, Campo } from '../../components/ui'
import { api } from '../../lib/api'
import type { Domiciliario } from '../../lib/tipos'
import { telefonoLegible, useDomiciliarios } from '../clientes/datos'

export interface DatosDomicilio {
  domiciliarioId: string
  direccion: string
  telefono: string
}

/** Elegir quién lleva el pedido; si no está, se agrega ahí mismo (no es usuario del sistema). */
export function SelectorDomiciliario({
  valor,
  alCambiar,
  error,
}: {
  valor: string
  alCambiar: (id: string) => void
  error?: string
}) {
  const domiciliarios = useDomiciliarios()
  const [creando, setCreando] = useState(false)
  return (
    <div className="flex items-end gap-2">
      <Buscador
        className="min-w-0 flex-1"
        etiqueta="Domiciliario"
        placeholder={domiciliarios.data?.length === 0 ? 'Agrega el primero con +' : 'Quién lo lleva'}
        opciones={(domiciliarios.data ?? []).map((d) => ({ valor: d.id, texto: d.nombre, detalle: telefonoLegible(d.telefono) }))}
        valor={valor}
        alCambiar={alCambiar}
        error={error}
      />
      <button
        type="button"
        onClick={() => setCreando(true)}
        aria-label="Agregar domiciliario"
        title="Agregar domiciliario"
        className="grid size-12 shrink-0 place-items-center rounded-control border border-dorado-claro bg-blanco hover:border-dorado-borde"
      >
        <Plus aria-hidden className="size-5" strokeWidth={1.7} />
      </button>
      <DialogoDomiciliario
        abierto={creando}
        alCerrar={() => setCreando(false)}
        alCrear={(d) => {
          setCreando(false)
          alCambiar(d.id)
        }}
      />
    </div>
  )
}

export function DialogoDomiciliario({
  abierto,
  alCerrar,
  alCrear,
}: {
  abierto: boolean
  alCerrar: () => void
  alCrear: (d: Domiciliario) => void
}) {
  const clienteQuery = useQueryClient()
  const [nombre, setNombre] = useState('')
  const [telefono, setTelefono] = useState('')
  const crear = useMutation({
    mutationFn: () =>
      api<Domiciliario>('/domiciliarios', { method: 'POST', json: { nombre: nombre.trim(), telefono: telefono.trim() || null } }),
    onSuccess: (d) => {
      void clienteQuery.invalidateQueries({ queryKey: ['domiciliarios'] })
      setNombre('')
      setTelefono('')
      alCrear(d)
    },
  })
  return (
    <Dialogo abierto={abierto} alCerrar={alCerrar} titulo="Nuevo domiciliario">
      <form
        noValidate
        className="grid gap-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (nombre.trim().length >= 2) crear.mutate()
        }}
      >
        <Campo etiqueta="Nombre" value={nombre} maxLength={80} autoComplete="off" onChange={(e) => setNombre(e.target.value)} />
        <Campo etiqueta="Teléfono" inputMode="tel" value={telefono} maxLength={30} autoComplete="off" onChange={(e) => setTelefono(e.target.value)} />
        <p className="text-sm text-cafe-suave">No es un usuario del sistema: solo se elige al vender y se le entrega lo suyo al cerrar la caja.</p>
        {crear.isError && <Aviso>{crear.error.message}</Aviso>}
        <Boton type="submit" disabled={crear.isPending || nombre.trim().length < 2}>
          {crear.isPending ? 'Guardando…' : 'Agregar domiciliario'}
        </Boton>
      </form>
    </Dialogo>
  )
}

/** Dirección, teléfono y domiciliario de una entrega a domicilio (RF-13). */
export function CamposDomicilio({
  datos,
  alCambiar,
  intento,
}: {
  datos: DatosDomicilio
  alCambiar: (d: DatosDomicilio) => void
  /** Ya se intentó cobrar: se marcan los campos que faltan. */
  intento?: boolean
}) {
  return (
    <div className="grid gap-3">
      <Campo
        etiqueta="Dirección de entrega"
        value={datos.direccion}
        maxLength={200}
        autoComplete="off"
        onChange={(e) => alCambiar({ ...datos, direccion: e.target.value })}
        error={intento && !datos.direccion.trim() ? 'Escribe la dirección.' : undefined}
      />
      <Campo
        etiqueta="Teléfono de quien recibe"
        inputMode="tel"
        value={datos.telefono}
        maxLength={30}
        autoComplete="off"
        onChange={(e) => alCambiar({ ...datos, telefono: e.target.value })}
      />
      <SelectorDomiciliario
        valor={datos.domiciliarioId}
        alCambiar={(id) => alCambiar({ ...datos, domiciliarioId: id })}
        error={intento && !datos.domiciliarioId ? 'Elige quién lo lleva.' : undefined}
      />
    </div>
  )
}
