import { api, ErrorApi, fijarToken, renovarSesion } from './api'

const json = (cuerpo: unknown, status = 200) => new Response(JSON.stringify(cuerpo), { status })
const TOKEN = { access_token: 'nuevo', expira_en: '', usuario: {}, sede: {} }
const ROTADO = { codigo: 'REFRESH_ROTADO', mensaje: 'La sesión se renovó en otra pestaña.', detalle: {} }

afterEach(() => {
  vi.unstubAllGlobals()
  fijarToken(null)
})

describe('renovación de sesión', () => {
  it('reintenta si otra pestaña renovó al mismo tiempo', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(json(ROTADO, 401)).mockResolvedValueOnce(json(TOKEN))
    vi.stubGlobal('fetch', fetch)
    await expect(renovarSesion()).resolves.toMatchObject({ access_token: 'nuevo' })
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('no reintenta si la sesión fue cerrada por seguridad', async () => {
    const fetch = vi.fn().mockResolvedValue(json({ codigo: 'REFRESH_REUTILIZADO', mensaje: 'x', detalle: {} }, 401))
    vi.stubGlobal('fetch', fetch)
    await expect(renovarSesion()).rejects.toMatchObject({ codigo: 'REFRESH_REUTILIZADO' })
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('llamadas simultáneas comparten una sola renovación', async () => {
    const fetch = vi.fn().mockResolvedValue(json(TOKEN))
    vi.stubGlobal('fetch', fetch)
    await Promise.all([renovarSesion(), renovarSesion(), renovarSesion()])
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})

describe('api', () => {
  it('ante un 401 renueva y repite la petición con el token nuevo', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json({ codigo: 'TOKEN_EXPIRADO', mensaje: 'x', detalle: {} }, 401))
      .mockResolvedValueOnce(json(TOKEN))
      .mockResolvedValueOnce(json({ ok: true }))
    vi.stubGlobal('fetch', fetch)
    fijarToken('viejo')
    await expect(api('/usuarios')).resolves.toEqual({ ok: true })
    const ultima = fetch.mock.calls[2][1] as RequestInit
    expect(new Headers(ultima.headers).get('Authorization')).toBe('Bearer nuevo')
  })

  it('convierte los errores del API en ErrorApi con código y mensaje', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ codigo: 'EMAIL_DUPLICADO', mensaje: 'Ya existe.', detalle: {} }, 409)))
    const error = await api('/usuarios', { method: 'POST', json: {} }).catch((e) => e)
    expect(error).toBeInstanceOf(ErrorApi)
    expect(error).toMatchObject({ estado: 409, codigo: 'EMAIL_DUPLICADO', message: 'Ya existe.' })
  })

  it('envía la clave de idempotencia cuando se indica', async () => {
    const fetch = vi.fn().mockResolvedValue(json({}))
    vi.stubGlobal('fetch', fetch)
    await api('/ventas', { method: 'POST', json: {}, idempotencia: 'abc-123' })
    expect(new Headers((fetch.mock.calls[0][1] as RequestInit).headers).get('Idempotency-Key')).toBe('abc-123')
  })
})
