import { createContext, useContext } from 'react'

export type TonoAviso = 'exito' | 'error'

export interface Avisos {
  /** Muestra un aviso breve abajo de la pantalla; desaparece solo a los 4 s. */
  avisar: (texto: string, tono?: TonoAviso) => void
}

export const ContextoAvisos = createContext<Avisos>({ avisar: () => {} })

export const useAvisos = () => useContext(ContextoAvisos)
