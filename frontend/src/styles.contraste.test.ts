/**
 * Contraste WCAG AA de los pares de colores que se usan para texto. Lee los tokens de
 * styles.css, así que cambiar un color que rompa el contraste hace fallar la prueba.
 */
// @vitest-environment node
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const css = readFileSync(fileURLToPath(new URL('./styles.css', import.meta.url)), 'utf8')
const tokens = Object.fromEntries(
  [...css.matchAll(/--color-([\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]),
)

function luminancia(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contraste(a: string, b: string): number {
  const [l1, l2] = [luminancia(a), luminancia(b)].sort((x, y) => y - x)
  return (l1 + 0.05) / (l2 + 0.05)
}

// [texto, fondo] para texto normal (AA = 4,5:1)
const PARES: [string, string][] = [
  ['cafe', 'crema'],
  ['cafe', 'blanco'],
  ['cafe', 'rosa'],
  ['cafe', 'rosa-suave'],
  ['cafe-medio', 'blanco'],
  ['cafe-medio', 'crema'],
  ['cafe-medio', 'rosa-suave'],
  ['cafe-suave', 'blanco'],
  ['cafe-suave', 'crema'],
  ['fucsia', 'blanco'],
  ['fucsia', 'crema'],
  ['blanco', 'fucsia'],
  ['blanco', 'fucsia-oscuro'],
  ['fucsia-oscuro', 'rosa-suave'],
  ['dorado-texto', 'rosa'],
  ['dorado-texto', 'arena'],
  ['dorado-texto', 'blanco'],
  // El verde del mockup (#2E8A5F) no llega a AA como texto: solo para puntos e interruptores.
  ['exito-texto', 'rosa-suave'],
  ['exito-texto', 'exito-fondo'],
  ['peligro-texto', 'peligro-fondo'],
  ['peligro-texto', 'blanco'],
  ['aviso-texto', 'aviso-fondo'],
]

describe('contraste AA de los tokens', () => {
  it.each(PARES)('%s sobre %s', (texto, fondo) => {
    expect(tokens[texto], `falta el token ${texto}`).toBeDefined()
    expect(tokens[fondo], `falta el token ${fondo}`).toBeDefined()
    expect(contraste(tokens[texto], tokens[fondo])).toBeGreaterThanOrEqual(4.5)
  })
})
