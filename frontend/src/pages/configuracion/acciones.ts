import { useMutation, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { useState } from 'react'
import { ErrorApi } from '../../lib/api'

/** Selección de la lista: un id, "nuevo" o nada. */
export type Seleccion = string | 'nuevo' | null

/**
 * Selección de la lista + versión del formulario. El formulario se reinicia solo cuando se
 * elige otra fila o "Nuevo"; al guardar se conserva (y con él el aviso "Cambios guardados").
 */
export function useSeleccion() {
  const [sel, setSel] = useState<Seleccion>(null)
  const [version, setVersion] = useState(0)
  return {
    sel,
    version,
    /** Elegir desde la lista: reinicia el formulario. */
    elegir: (s: Seleccion) => {
      setVersion((v) => v + 1)
      elegir(setSel, s)
    },
    /** Tras guardar: apunta al registro guardado sin reiniciar el formulario. */
    fijar: (s: Seleccion) => {
      if (s === null) setVersion((v) => v + 1)
      setSel(s)
    },
  }
}

function elegir(setSel: (s: Seleccion) => void, s: Seleccion) {
  setSel(s)
  // En celular el panel queda debajo de la lista: se lleva a la vista.
  if (window.matchMedia?.('(max-width: 1023px)').matches) {
    requestAnimationFrame(() =>
      document.getElementById('panel-detalle')?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
    )
  }
}

/**
 * Mutación que invalida las consultas indicadas al terminar y expone el mensaje de error del
 * API para mostrarlo en el panel.
 */
export function useGuardar<E, S>(fn: (e: E) => Promise<S>, invalidar: QueryKey[], alTerminar?: (s: S) => void) {
  const cliente = useQueryClient()
  const [error, setError] = useState<string>()
  const m = useMutation({
    mutationFn: fn,
    onMutate: () => setError(undefined),
    onSuccess: async (s) => {
      await Promise.all(invalidar.map((k) => cliente.invalidateQueries({ queryKey: k })))
      alTerminar?.(s)
    },
    onError: (e) => setError(mensajeDeError(e)),
  })
  return { ...m, error }
}

export function mensajeDeError(e: unknown): string {
  if (e instanceof ErrorApi) {
    if (e.codigo === 'VALIDACION') return 'Revisa los datos: hay campos con un formato que no es válido.'
    return e.message
  }
  return 'No pudimos guardar los cambios. Intenta de nuevo.'
}

export const vacioANulo = (s: string) => (s.trim() === '' ? null : s.trim())
