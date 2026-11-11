import { CircleAlert, CircleCheck, X } from 'lucide-react'
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import { unir } from '../lib/clases'
import { ContextoAvisos, type TonoAviso } from './usarAvisos'

interface Aviso {
  id: number
  texto: string
  tono: TonoAviso
}

/** Avisos emergentes ("toasts"): confirmaciones y errores que no bloquean el trabajo. */
export function ProveedorAvisos({ children }: { children: ReactNode }) {
  const [avisos, setAvisos] = useState<Aviso[]>([])
  const siguiente = useRef(0)

  const quitar = useCallback((id: number) => setAvisos((a) => a.filter((x) => x.id !== id)), [])
  const avisar = useCallback(
    (texto: string, tono: TonoAviso = 'exito') => {
      const id = ++siguiente.current
      setAvisos((a) => [...a.slice(-2), { id, texto, tono }])
      setTimeout(() => quitar(id), tono === 'error' ? 6000 : 4000)
    },
    [quitar],
  )
  const valor = useMemo(() => ({ avisar }), [avisar])

  return (
    <ContextoAvisos.Provider value={valor}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 p-4 pb-[max(1rem,env(safe-area-inset-bottom))]"
      >
        {avisos.map((a) => (
          <div
            key={a.id}
            role={a.tono === 'error' ? 'alert' : 'status'}
            className={unir(
              'pointer-events-auto flex max-w-[min(480px,100%)] items-center gap-3 rounded-control border py-3 pr-2 pl-4 text-[15px] font-semibold shadow-[0_8px_24px_-12px_rgb(74_52_40/0.35)] motion-safe:animate-[entrar_180ms_ease-out]',
              a.tono === 'exito'
                ? 'border-exito/25 bg-exito-fondo text-exito-texto'
                : 'border-peligro/25 bg-peligro-fondo text-peligro-texto',
            )}
          >
            {a.tono === 'exito' ? (
              <CircleCheck aria-hidden className="size-5 shrink-0" />
            ) : (
              <CircleAlert aria-hidden className="size-5 shrink-0" />
            )}
            <span className="min-w-0 flex-1">{a.texto}</span>
            <button
              type="button"
              onClick={() => quitar(a.id)}
              aria-label="Cerrar aviso"
              className="grid size-9 shrink-0 place-items-center rounded-control opacity-70 hover:opacity-100"
            >
              <X aria-hidden className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </ContextoAvisos.Provider>
  )
}
