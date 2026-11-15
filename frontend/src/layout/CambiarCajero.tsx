import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useSesion, useYo } from '../auth/contexto'
import { Dialogo } from '../components/Dialogo'
import { TecladoPin } from '../components/TecladoPin'
import { Boton, Campo } from '../components/ui'
import { useAvisos } from '../components/usarAvisos'
import { api, ErrorApi, type TokenSalida } from '../lib/api'
import type { Cajero } from '../lib/tipos'

type Paso = { tipo: 'lista' } | { tipo: 'pin'; cajero: Cajero } | { tipo: 'definir' }

/**
 * Cambio rápido de cajero en un equipo con sesión abierta (#35): se elige quién y se escribe
 * su PIN. Las ventas siguientes quedan a nombre de esa persona.
 */
export function CambiarCajero({ abierto, alCerrar }: { abierto: boolean; alCerrar: () => void }) {
  const [paso, setPaso] = useState<Paso>({ tipo: 'lista' })
  const cerrar = () => {
    setPaso({ tipo: 'lista' })
    alCerrar()
  }
  const titulo = paso.tipo === 'pin' ? paso.cajero.nombre : paso.tipo === 'definir' ? 'Mi PIN' : '¿Quién atiende?'
  return (
    <Dialogo abierto={abierto} alCerrar={cerrar} titulo={titulo} rotulo="Cambiar de cajero">
      {paso.tipo === 'lista' && (
        <ListaCajeros alElegir={(cajero) => setPaso({ tipo: 'pin', cajero })} alDefinir={() => setPaso({ tipo: 'definir' })} />
      )}
      {paso.tipo === 'pin' && <IngresoPin cajero={paso.cajero} alVolver={() => setPaso({ tipo: 'lista' })} alEntrar={cerrar} />}
      {paso.tipo === 'definir' && <DefinirPin alTerminar={() => setPaso({ tipo: 'lista' })} />}
    </Dialogo>
  )
}

function ListaCajeros({ alElegir, alDefinir }: { alElegir: (c: Cajero) => void; alDefinir: () => void }) {
  const yo = useYo()
  const cajeros = useQuery({ queryKey: ['cajeros'], queryFn: () => api<Cajero[]>('/auth/cajeros') })
  const otros = (cajeros.data ?? []).filter((c) => c.id !== yo.usuario.id)
  return (
    <div>
      {cajeros.isPending && <p className="text-cafe-medio">Cargando…</p>}
      {cajeros.isSuccess && otros.length === 0 && (
        <p className="text-cafe-medio">Nadie más de esta sede tiene PIN todavía. Cada persona lo define desde aquí con su contraseña.</p>
      )}
      <ul className="grid gap-2">
        {otros.map((c) => (
          <li key={c.id}>
            <button
              type="button"
              onClick={() => alElegir(c)}
              className="flex h-14 w-full items-center rounded-control border border-dorado-claro bg-crema px-4 text-left text-[17px] font-semibold hover:border-dorado-borde"
            >
              {c.nombre}
            </button>
          </li>
        ))}
      </ul>
      <button type="button" onClick={alDefinir} className="mt-4 text-[15px] font-semibold text-fucsia hover:underline">
        Definir o cambiar mi PIN
      </button>
    </div>
  )
}

function IngresoPin({ cajero, alVolver, alEntrar }: { cajero: Cajero; alVolver: () => void; alEntrar: () => void }) {
  const { adoptar } = useSesion()
  const { avisar } = useAvisos()
  const [pin, setPin] = useState('')
  const entrar = useMutation({
    mutationFn: () => api<TokenSalida>('/auth/pin', { method: 'POST', json: { usuario_id: cajero.id, pin } }),
    onSuccess: async (datos) => {
      await adoptar(datos)
      avisar(`Ahora atiende ${datos.usuario.nombre}`)
      alEntrar()
    },
    onError: () => setPin(''),
  })
  return (
    <div>
      <p className="mb-4 text-center text-cafe-medio">Escribe tu PIN</p>
      <TecladoPin
        valor={pin}
        alCambiar={(v) => {
          entrar.reset()
          setPin(v)
        }}
        alEnviar={() => entrar.mutate()}
        ocupado={entrar.isPending}
        error={entrar.error instanceof Error ? entrar.error.message : undefined}
      />
      <button type="button" onClick={alVolver} className="mt-4 text-[15px] font-semibold text-fucsia hover:underline">
        Elegir otra persona
      </button>
    </div>
  )
}

function DefinirPin({ alTerminar }: { alTerminar: () => void }) {
  const { avisar } = useAvisos()
  const [clave, setClave] = useState('')
  const [pin, setPin] = useState('')
  const guardar = useMutation({
    mutationFn: () => api('/auth/pin', { method: 'PUT', json: { clave_actual: clave, pin } }),
    onSuccess: () => {
      avisar('Tu PIN quedó guardado')
      alTerminar()
    },
  })
  const pinValido = /^\d{4,6}$/.test(pin)
  const error = guardar.error instanceof ErrorApi ? guardar.error : null
  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        if (pinValido && clave) guardar.mutate()
      }}
    >
      <p className="text-cafe-medio">Con el PIN cambias de cajero sin escribir tu correo. Confirma con tu contraseña.</p>
      <Campo
        etiqueta="Tu contraseña"
        type="password"
        autoComplete="current-password"
        value={clave}
        onChange={(e) => setClave(e.target.value)}
        error={error?.codigo === 'CREDENCIALES_INVALIDAS' ? error.message : undefined}
      />
      <Campo
        etiqueta="PIN nuevo (4 a 6 números)"
        inputMode="numeric"
        autoComplete="off"
        maxLength={6}
        value={pin}
        onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
        error={error && error.codigo !== 'CREDENCIALES_INVALIDAS' ? error.message : undefined}
      />
      <div className="flex justify-end gap-3">
        <Boton variante="secundario" onClick={alTerminar}>
          Volver
        </Boton>
        <Boton type="submit" disabled={!pinValido || !clave || guardar.isPending}>
          Guardar PIN
        </Boton>
      </div>
    </form>
  )
}
