import { useRef } from 'react'

/**
 * Clave de idempotencia por contenido: el mismo cuerpo reintenta con la misma clave (si la
 * primera petición sí llegó, el backend devuelve ese resultado sin duplicarlo); un cuerpo
 * distinto es otra operación y lleva clave nueva.
 */
export function useClaveIdempotencia() {
  const ultima = useRef<{ cuerpo: string; clave: string } | null>(null)
  return {
    para(cuerpo: unknown): string {
      const texto = JSON.stringify(cuerpo)
      if (ultima.current?.cuerpo !== texto) ultima.current = { cuerpo: texto, clave: crypto.randomUUID() }
      return ultima.current.clave
    },
    olvidar() {
      ultima.current = null
    },
  }
}
