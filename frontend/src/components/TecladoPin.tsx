import { Delete } from 'lucide-react'
import { useEffect } from 'react'
import { unir } from '../lib/clases'

/**
 * Teclado numérico para el PIN (4 a 6 dígitos): botones grandes para pantalla táctil y también
 * acepta el teclado físico. Los puntos muestran cuántos dígitos van, nunca los dígitos.
 */
export function TecladoPin({
  valor,
  alCambiar,
  alEnviar,
  error,
  ocupado,
  textoEnviar = 'Entrar',
}: {
  valor: string
  alCambiar: (v: string) => void
  alEnviar: () => void
  error?: string
  ocupado?: boolean
  textoEnviar?: string
}) {
  const listo = valor.length >= 4 && !ocupado

  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => {
      if (ocupado || (e.target instanceof HTMLInputElement)) return
      if (/^\d$/.test(e.key) && valor.length < 6) alCambiar(valor + e.key)
      else if (e.key === 'Backspace') alCambiar(valor.slice(0, -1))
      else if (e.key === 'Enter' && listo) alEnviar()
      else return
      e.preventDefault()
    }
    document.addEventListener('keydown', alTeclear)
    return () => document.removeEventListener('keydown', alTeclear)
  }, [valor, alCambiar, alEnviar, listo, ocupado])

  const tecla = 'grid h-14 place-items-center rounded-control border border-dorado-claro bg-crema text-2xl font-semibold hover:border-dorado-borde disabled:opacity-50'

  return (
    <div>
      <div className="flex h-8 items-center justify-center gap-3" role="status" aria-label={`PIN: ${valor.length} dígitos`}>
        {Array.from({ length: Math.max(4, valor.length) }, (_, i) => (
          <span
            key={i}
            aria-hidden
            className={unir('size-3.5 rounded-full border-2 border-fucsia', i < valor.length && 'bg-fucsia')}
          />
        ))}
      </div>
      {error && (
        <p role="alert" className="mt-2 text-center text-sm text-peligro-texto">
          {error}
        </p>
      )}
      <div className="mt-4 grid grid-cols-3 gap-2.5">
        {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => (
          <button
            key={d}
            type="button"
            className={tecla}
            disabled={ocupado || valor.length >= 6}
            onClick={() => alCambiar(valor + d)}
          >
            {d}
          </button>
        ))}
        <button
          type="button"
          className={tecla}
          aria-label="Borrar un dígito"
          disabled={ocupado || valor.length === 0}
          onClick={() => alCambiar(valor.slice(0, -1))}
        >
          <Delete aria-hidden className="size-6" strokeWidth={1.6} />
        </button>
        <button
          type="button"
          className={tecla}
          disabled={ocupado || valor.length >= 6}
          onClick={() => alCambiar(valor + '0')}
        >
          0
        </button>
        <button
          type="button"
          disabled={!listo}
          onClick={alEnviar}
          className="h-14 rounded-control bg-fucsia text-[17px] font-bold text-white hover:bg-fucsia-oscuro disabled:cursor-not-allowed disabled:opacity-50"
        >
          {textoEnviar}
        </button>
      </div>
    </div>
  )
}
