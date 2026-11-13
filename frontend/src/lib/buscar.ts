/** Búsqueda de texto tolerante: sin importar tildes, mayúsculas ni el orden de las palabras. */

const normalizar = (s: string) =>
  s
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()

/** Cada palabra escrita debe aparecer en el texto, en cualquier orden y posición. */
export function coincide(texto: string, consulta: string): boolean {
  const t = normalizar(texto)
  return normalizar(consulta)
    .split(/\s+/)
    .filter(Boolean)
    .every((palabra) => t.includes(palabra))
}
