import { CircleAlert, Eye, EyeOff } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router'
import { useSesion } from '../auth/contexto'
import { Boton, Campo } from '../components/ui'
import { Cargando } from '../layout/AppLayout'
import { ErrorApi, type SedeResumen } from '../lib/api'

export function Ingresar() {
  const { estado, iniciar } = useSesion()
  const [email, setEmail] = useState('')
  const [clave, setClave] = useState('')
  const [verClave, setVerClave] = useState(false)
  const [sedes, setSedes] = useState<SedeResumen[] | null>(null)
  const [sedeId, setSedeId] = useState<string>()
  const [error, setError] = useState<string>()
  const [enviando, setEnviando] = useState(false)

  if (estado.tipo === 'cargando') return <Cargando />
  if (estado.tipo === 'autenticado') return <Navigate to="/" replace />

  async function enviar(e: FormEvent) {
    e.preventDefault()
    // Se leen los valores del formulario: el autocompletado del navegador no siempre avisa a React.
    const datos = new FormData(e.currentTarget as HTMLFormElement)
    const correo = String(datos.get('email') ?? '').trim()
    const contrasena = String(datos.get('password') ?? '')
    if (!correo || !contrasena) {
      setError('Escribe tu correo y tu contraseña para entrar.')
      return
    }
    setError(undefined)
    setEnviando(true)
    try {
      await iniciar(correo, contrasena, sedeId)
    } catch (err) {
      if (err instanceof ErrorApi && err.codigo === 'SEDE_REQUERIDA') {
        const lista = (err.detalle.sedes as SedeResumen[]) ?? []
        setSedes(lista)
        setSedeId(lista[0]?.id)
      } else {
        setError(err instanceof Error ? err.message : 'No pudimos iniciar la sesión. Intenta de nuevo.')
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <main className="grid min-h-dvh place-items-center bg-rosa px-4 py-10">
      <div className="w-full max-w-[400px] rounded-tarjeta border border-dorado-claro bg-crema px-6 py-9 sm:px-9">
        <div className="flex flex-col items-center text-center">
          <img src="/logo.png" alt="" className="size-24 rounded-full" />
          <h1 className="mt-4 font-serif text-[40px] leading-none font-semibold tracking-[0.02em]">
            ZUQUI&apos;S
          </h1>
          <p className="mt-2 text-xs font-semibold tracking-[0.2em] text-dorado-texto">REPOSTERÍA</p>
        </div>

        <form onSubmit={enviar} className="mt-8 flex flex-col gap-5" noValidate>
          <Campo
            etiqueta="Correo"
            name="email"
            type="email"
            autoComplete="username"
            inputMode="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Campo
            etiqueta="Contraseña"
            name="password"
            type={verClave ? 'text' : 'password'}
            autoComplete="current-password"
            required
            value={clave}
            onChange={(e) => setClave(e.target.value)}
            extra={
              <button
                type="button"
                onClick={() => setVerClave((v) => !v)}
                aria-label={verClave ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                className="grid size-10 place-items-center rounded-control text-cafe-suave hover:text-cafe"
              >
                {verClave ? <EyeOff className="size-5" aria-hidden /> : <Eye className="size-5" aria-hidden />}
              </button>
            }
          />

          {sedes && (
            <fieldset>
              <legend className="mb-1.5 text-sm font-semibold">Sede</legend>
              <div className="flex flex-col gap-2">
                {sedes.map((s) => (
                  <label
                    key={s.id}
                    className="flex h-12 cursor-pointer items-center gap-3 rounded-control border border-dorado-claro bg-blanco px-4 has-checked:border-fucsia has-checked:bg-rosa-suave"
                  >
                    <input
                      type="radio"
                      name="sede"
                      value={s.id}
                      checked={sedeId === s.id}
                      onChange={() => setSedeId(s.id)}
                      className="accent-fucsia"
                    />
                    {s.nombre}
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          {error && (
            <p role="alert" className="flex gap-2 rounded-control bg-peligro-fondo p-3 text-sm text-peligro-texto">
              <CircleAlert className="mt-px size-[18px] shrink-0" aria-hidden />
              {error}
            </p>
          )}

          <Boton type="submit" disabled={enviando} className="mt-1 w-full">
            {enviando ? 'Entrando…' : sedes ? 'Entrar a la sede' : 'Entrar'}
          </Boton>
        </form>
      </div>
    </main>
  )
}
