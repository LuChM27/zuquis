/**
 * Cliente HTTP del API. El token de acceso vive solo en memoria; el de renovación va en una
 * cookie HttpOnly que el navegador envía a /api/v1/auth. Ante un 401 se renueva una vez y se
 * reintenta. Los errores llegan como {codigo, mensaje, detalle} (ver backend/app/shared/errores.py).
 */
export const BASE = '/api/v1'

export class ErrorApi extends Error {
  readonly estado: number
  readonly codigo: string
  readonly detalle: Record<string, unknown>

  constructor(estado: number, codigo: string, mensaje: string, detalle: Record<string, unknown> = {}) {
    super(mensaje)
    this.estado = estado
    this.codigo = codigo
    this.detalle = detalle
  }
}

export interface SedeResumen {
  id: string
  nombre: string
}
export interface UsuarioResumen {
  id: string
  nombre: string
  email: string
}
export interface TokenSalida {
  access_token: string
  expira_en: string
  usuario: UsuarioResumen
  sede: SedeResumen
}
export interface YoSalida {
  usuario: UsuarioResumen
  sede: SedeResumen
  sedes: SedeResumen[]
  roles: string[]
  permisos: string[]
}

let tokenAcceso: string | null = null
let renovando: Promise<TokenSalida> | null = null
let alExpirar: () => void = () => {}

export function fijarToken(token: string | null): void {
  tokenAcceso = token
}

/** Se llama cuando la sesión no se puede renovar (para volver al login). */
export function alExpirarSesion(fn: () => void): void {
  alExpirar = fn
}

async function leerError(r: Response): Promise<ErrorApi> {
  try {
    const cuerpo = await r.json()
    return new ErrorApi(r.status, cuerpo.codigo ?? 'ERROR', cuerpo.mensaje ?? 'Algo salió mal.', cuerpo.detalle ?? {})
  } catch {
    return new ErrorApi(r.status, 'ERROR', 'No pudimos comunicarnos con el servidor. Intenta de nuevo.')
  }
}

async function crudo(ruta: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (tokenAcceso) headers.set('Authorization', `Bearer ${tokenAcceso}`)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  try {
    return await fetch(`${BASE}${ruta}`, { ...init, headers, credentials: 'include' })
  } catch {
    throw new ErrorApi(0, 'SIN_CONEXION', 'No hay conexión con el servidor. Revisa la red e intenta de nuevo.')
  }
}

/** Renueva la sesión con la cookie. Varias llamadas simultáneas comparten una sola renovación. */
export function renovarSesion(): Promise<TokenSalida> {
  renovando ??= (async () => {
    try {
      const r = await crudo('/auth/refresh', { method: 'POST' })
      if (!r.ok) throw await leerError(r)
      const datos: TokenSalida = await r.json()
      fijarToken(datos.access_token)
      return datos
    } finally {
      renovando = null
    }
  })()
  return renovando
}

interface Opciones extends Omit<RequestInit, 'body'> {
  json?: unknown
  body?: BodyInit
  /** Clave para operaciones que mueven dinero o inventario (reintento seguro sin duplicar). */
  idempotencia?: string
}

export async function api<T>(ruta: string, opciones: Opciones = {}): Promise<T> {
  const { json, idempotencia, ...init } = opciones
  const headers = new Headers(init.headers)
  if (idempotencia) headers.set('Idempotency-Key', idempotencia)
  const peticion: RequestInit = { ...init, headers, body: json !== undefined ? JSON.stringify(json) : init.body }

  let r = await crudo(ruta, peticion)
  if (r.status === 401 && !ruta.startsWith('/auth/')) {
    try {
      await renovarSesion()
    } catch {
      fijarToken(null)
      alExpirar()
      throw await leerError(r)
    }
    r = await crudo(ruta, peticion)
  }
  if (!r.ok) throw await leerError(r)
  if (r.status === 204) return undefined as T
  return r.json() as Promise<T>
}
