import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Dialogo } from '../../components/Dialogo'
import { AreaTexto, Aviso, Casilla } from '../../components/formulario'
import { Boton, Campo } from '../../components/ui'
import { api, ErrorApi } from '../../lib/api'
import type { Cliente } from '../../lib/tipos'
import { telefonoLegible } from './datos'

/** Aviso de privacidad (Ley 1581 de 2012). Texto a validar con el negocio. */
export const AVISO_DATOS =
  'Zuqui’s guarda tu nombre, teléfono y dirección solo para tus pedidos y domicilios. Puedes pedir que los corrijamos o borremos cuando quieras.'

interface Borrador {
  nombre: string
  telefono: string
  direccion: string
  notas: string
  autoriza: boolean
}

const desde = (c?: Cliente | null): Borrador => ({
  nombre: c?.nombre ?? '',
  telefono: telefonoLegible(c?.telefono),
  direccion: c?.direccion ?? '',
  notas: c?.notas ?? '',
  autoriza: c?.autoriza_datos ?? false,
})

/**
 * Crear o editar un cliente. Si el teléfono ya es de otro cliente, el backend avisa
 * (TELEFONO_REPETIDO) y aquí se decide: usar ese cliente o guardar de todos modos.
 */
export function FormCliente({
  cliente,
  nombreInicial = '',
  alGuardar,
  alUsarExistente,
  alCancelar,
}: {
  cliente?: Cliente | null
  nombreInicial?: string
  alGuardar: (c: Cliente) => void
  /** Si se ofrece, el aviso de teléfono repetido permite elegir al cliente que ya existe. */
  alUsarExistente?: (c: Cliente) => void
  alCancelar?: () => void
}) {
  const clienteQuery = useQueryClient()
  const [b, setB] = useState<Borrador>(() => ({ ...desde(cliente), nombre: cliente?.nombre ?? nombreInicial }))
  const [intento, setIntento] = useState(false)
  const [repetido, setRepetido] = useState<Cliente | null>(null)
  const nombreValido = b.nombre.trim().length >= 2

  const guardar = useMutation({
    mutationFn: (permitirRepetido: boolean) => {
      const cuerpo = {
        nombre: b.nombre.trim(),
        telefono: b.telefono.trim() || null,
        direccion: b.direccion.trim() || null,
        notas: b.notas.trim() || null,
        autoriza_datos: b.autoriza,
        permitir_telefono_repetido: permitirRepetido,
      }
      return cliente
        ? api<Cliente>(`/clientes/${cliente.id}`, { method: 'PATCH', json: cuerpo })
        : api<Cliente>('/clientes', { method: 'POST', json: cuerpo })
    },
    onSuccess: (c) => {
      setRepetido(null)
      void clienteQuery.invalidateQueries({ queryKey: ['clientes'] })
      alGuardar(c)
    },
    onError: (e) => {
      if (e instanceof ErrorApi && e.codigo === 'TELEFONO_REPETIDO') setRepetido(e.detalle.cliente as Cliente)
    },
  })
  const error = guardar.error instanceof ErrorApi && guardar.error.codigo !== 'TELEFONO_REPETIDO' ? guardar.error.message : null

  return (
    <form
      noValidate
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        setIntento(true)
        if (nombreValido) guardar.mutate(false)
      }}
    >
      <Campo
        etiqueta="Nombre"
        value={b.nombre}
        maxLength={120}
        autoComplete="off"
        onChange={(e) => setB({ ...b, nombre: e.target.value })}
        error={intento && !nombreValido ? 'Escribe el nombre del cliente.' : undefined}
      />
      <Campo
        etiqueta="Teléfono"
        inputMode="tel"
        value={b.telefono}
        maxLength={30}
        autoComplete="off"
        onChange={(e) => {
          setRepetido(null)
          setB({ ...b, telefono: e.target.value })
        }}
      />
      <Campo etiqueta="Dirección" value={b.direccion} maxLength={200} autoComplete="off" onChange={(e) => setB({ ...b, direccion: e.target.value })} />
      <AreaTexto etiqueta="Notas" value={b.notas} maxLength={500} onChange={(e) => setB({ ...b, notas: e.target.value })} />
      <Casilla
        etiqueta="Autoriza el tratamiento de sus datos"
        ayuda={AVISO_DATOS}
        marcada={b.autoriza}
        alCambiar={(v) => setB({ ...b, autoriza: v })}
      />
      {repetido && (
        <div className="grid gap-3 rounded-control bg-aviso-fondo p-3.5">
          <p role="status" className="text-sm text-cafe-medio">
            <strong>{repetido.nombre}</strong> ya está registrado con el teléfono {telefonoLegible(repetido.telefono)}.
            ¿Es la misma persona?
          </p>
          <div className="flex flex-wrap gap-2">
            {alUsarExistente && (
              <Boton variante="secundario" className="h-10 px-4 text-[15px]" onClick={() => alUsarExistente(repetido)}>
                Usar a {repetido.nombre}
              </Boton>
            )}
            <Boton variante="secundario" className="h-10 px-4 text-[15px]" onClick={() => guardar.mutate(true)}>
              Guardar de todos modos
            </Boton>
          </div>
        </div>
      )}
      {error && <Aviso>{error}</Aviso>}
      <div className="flex flex-wrap justify-end gap-3">
        {alCancelar && (
          <Boton variante="secundario" onClick={alCancelar}>
            Cancelar
          </Boton>
        )}
        <Boton type="submit" disabled={guardar.isPending}>
          {guardar.isPending ? 'Guardando…' : cliente ? 'Guardar cambios' : 'Crear cliente'}
        </Boton>
      </div>
    </form>
  )
}

export function DialogoCliente({
  abierto,
  nombreInicial,
  alCerrar,
  alElegir,
}: {
  abierto: boolean
  nombreInicial?: string
  alCerrar: () => void
  alElegir: (c: Cliente) => void
}) {
  return (
    <Dialogo abierto={abierto} alCerrar={alCerrar} titulo="Nuevo cliente">
      <FormCliente nombreInicial={nombreInicial} alGuardar={alElegir} alUsarExistente={alElegir} alCancelar={alCerrar} />
    </Dialogo>
  )
}
