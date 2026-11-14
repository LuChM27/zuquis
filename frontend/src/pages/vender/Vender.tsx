import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Contrast } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useSesion } from '../../auth/contexto'
import { CampoDinero } from '../../components/CampoDinero'
import { Boton, Tarjeta, TituloTarjeta } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api, ErrorApi } from '../../lib/api'
import { agregar, calcular, carritoVacio, cuerpoVenta, editarLinea, pagosPara, quitarLinea, type Carrito } from '../../lib/carrito'
import { unir } from '../../lib/clases'
import { aplicarContraste, contrasteAlto } from '../../lib/contraste'
import { pesos } from '../../lib/formato'
import type { Autorizacion, Categoria, MetodoPago, Producto, Venta } from '../../lib/tipos'
import { useCaja } from '../caja/usarCaja'
import { Catalogo } from './Catalogo'
import { DialogoAutorizacion, DialogoDescuento, DialogoLinea, DialogoPropina, VentaRegistrada } from './Dialogos'
import { cobroVacio, type Cobro } from './logica'
import { PanelVenta } from './PanelVenta'

const SERVICIO = { local: 'En local', llevar: 'Para llevar', domicilio: 'Domicilio' }

/** Escritorio (≥ 1024 px): panel de venta fijo a la derecha. En celular, hoja completa. */
function useEscritorio(): boolean {
  const consulta = '(min-width: 1024px)'
  const [es, setEs] = useState(() => window.matchMedia?.(consulta).matches ?? true)
  useEffect(() => {
    const m = window.matchMedia?.(consulta)
    if (!m) return
    const alCambiar = () => setEs(m.matches)
    m.addEventListener('change', alCambiar)
    return () => m.removeEventListener('change', alCambiar)
  }, [])
  return es
}

/**
 * Clave de idempotencia por contenido: el mismo cuerpo reintenta con la misma clave (si la
 * primera petición sí llegó, el backend devuelve esa venta sin duplicarla); un cuerpo distinto
 * es otra venta y lleva clave nueva.
 */
function useClaveIdempotencia() {
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

export function Vender() {
  const caja = useCaja()
  if (caja.isPending) return <p className="p-10 text-cafe-medio">Cargando…</p>
  if (caja.isError) return <p className="p-10 text-peligro-texto">No pudimos revisar la caja. Recarga la página.</p>
  if (!caja.data.abierta) return <CajaCerrada />
  return <PuntoDeVenta />
}

function PuntoDeVenta() {
  const escritorio = useEscritorio()
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const categorias = useQuery({ queryKey: ['categorias'], queryFn: () => api<Categoria[]>('/categorias') })
  const productos = useQuery({ queryKey: ['productos', 'pos'], queryFn: () => api<Producto[]>('/productos') })
  const metodos = useQuery({ queryKey: ['metodos-pago'], queryFn: () => api<MetodoPago[]>('/metodos-pago') })
  const numero = useQuery({
    queryKey: ['ventas', 'proximo-numero'],
    queryFn: () => api<{ numero: number }>('/ventas/proximo-numero'),
    refetchInterval: 30_000,
  })

  const [carrito, setCarrito] = useState<Carrito>(() => carritoVacio())
  const [cobro, setCobro] = useState<Cobro>(cobroVacio)
  const [busqueda, setBusqueda] = useState('')
  const [categoria, setCategoria] = useState<string | null>(null)
  const [hojaAbierta, setHojaAbierta] = useState(false)
  const [lineaEditada, setLineaEditada] = useState<string | null>(null)
  const [editandoDescuento, setEditandoDescuento] = useState(false)
  const [editandoPropina, setEditandoPropina] = useState(false)
  const [pidiendoAutorizacion, setPidiendoAutorizacion] = useState(false)
  const [registrada, setRegistrada] = useState<Venta | null>(null)
  const [alto, setAlto] = useState(contrasteAlto)
  const clave = useClaveIdempotencia()

  const listaMetodos = useMemo(() => (metodos.data ?? []).filter((m) => m.activo).sort((a, b) => a.orden - b.orden), [metodos.data])
  const lista = useMemo(() => productos.data ?? [], [productos.data])
  const t = calcular(carrito)
  const enCarrito = useMemo(() => {
    const m = new Map<string, number>()
    for (const l of carrito.lineas) m.set(l.producto.id, (m.get(l.producto.id) ?? 0) + l.cantidad)
    return m
  }, [carrito.lineas])

  const vender = useMutation({
    mutationFn: (autorizacion: Autorizacion | null) => {
      const efectivo = new Set(listaMetodos.filter((m) => m.es_efectivo).map((m) => m.id))
      const pagos = pagosPara(t.cobrar, cobro.elegidos).map((p) => ({
        ...p,
        recibido: efectivo.has(p.metodoId) ? cobro.recibido : null,
      }))
      const cuerpo = { ...cuerpoVenta(carrito, pagos), autorizacion }
      return api<Venta>('/ventas', { method: 'POST', json: cuerpo, idempotencia: clave.para(cuerpo) })
    },
    onSuccess: (venta) => {
      clave.olvidar()
      setPidiendoAutorizacion(false)
      setHojaAbierta(false)
      setRegistrada(venta)
      setCarrito(carritoVacio(carrito.tipoServicio))
      setCobro(cobroVacio())
      void clienteQuery.invalidateQueries({ queryKey: ['ventas', 'proximo-numero'] })
      void clienteQuery.invalidateQueries({ queryKey: ['productos'] })
      void clienteQuery.invalidateQueries({ queryKey: ['caja'] })
    },
    onError: (e) => {
      if (e instanceof ErrorApi && e.codigo === 'DESCUENTO_REQUIERE_AUTORIZACION') {
        setPidiendoAutorizacion(true)
        return
      }
      if (e instanceof ErrorApi && e.codigo === 'AUTORIZACION_INVALIDA') return // se muestra en el diálogo
      if (e instanceof ErrorApi && e.codigo === 'CAJA_CERRADA') void clienteQuery.invalidateQueries({ queryKey: ['caja'] })
      avisar(
        e instanceof ErrorApi && e.codigo === 'SIN_CONEXION'
          ? 'Sin conexión: la venta no se confirmó. Toca Cobrar de nuevo; no se cobrará dos veces.'
          : e.message,
        'error',
      )
    },
  })

  const linea = carrito.lineas.find((l) => l.id === lineaEditada) ?? null
  const productoLinea = linea ? lista.find((p) => p.id === linea.producto.id) : undefined

  const panel = (
    <PanelVenta
      numero={numero.data?.numero}
      carrito={carrito}
      alCambiar={setCarrito}
      cobro={cobro}
      alCambiarCobro={setCobro}
      metodos={listaMetodos}
      alEditarLinea={setLineaEditada}
      alDescuento={() => setEditandoDescuento(true)}
      alPropina={() => setEditandoPropina(true)}
      alCobrar={() => vender.mutate(null)}
      cobrando={vender.isPending}
    />
  )

  const botonContraste = (
    <button
      type="button"
      aria-pressed={alto}
      onClick={() => {
        aplicarContraste(!alto)
        setAlto(!alto)
      }}
      title="Alto contraste"
      aria-label="Alto contraste"
      className={unir(
        'grid size-[54px] shrink-0 place-items-center rounded-control border bg-blanco',
        alto ? 'border-fucsia text-fucsia' : 'border-dorado-claro text-cafe-medio hover:border-dorado-borde',
      )}
    >
      <Contrast aria-hidden className="size-5" strokeWidth={1.8} />
    </button>
  )

  return (
    <div className="lg:flex lg:min-h-dvh">
      <div className="min-w-0 flex-1 px-4 pt-5 pb-32 lg:px-[37px] lg:pt-10 lg:pb-10">
        {productos.isPending || categorias.isPending ? (
          <p className="text-cafe-medio">Cargando la carta…</p>
        ) : (
          <Catalogo
            categorias={categorias.data ?? []}
            productos={lista}
            busqueda={busqueda}
            alBuscar={setBusqueda}
            categoria={categoria}
            alElegirCategoria={setCategoria}
            enCarrito={enCarrito}
            alAgregar={(p) => setCarrito((c) => agregar(c, { id: p.id, nombre: p.nombre, precio: p.precio }))}
            acciones={botonContraste}
          />
        )}
      </div>

      {escritorio ? (
        <aside aria-label="Venta actual" className="sticky top-0 h-dvh w-[376px] shrink-0 overflow-y-auto border-l border-dorado-claro bg-blanco xl:w-[420px]">
          {panel}
        </aside>
      ) : (
        <>
          {carrito.lineas.length > 0 && !hojaAbierta && (
            <div className="fixed inset-x-0 bottom-0 z-10 border-t border-dorado-claro bg-crema px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))]">
              <button
                type="button"
                onClick={() => setHojaAbierta(true)}
                className="flex h-[66px] w-full items-center justify-between rounded-[16px] bg-fucsia px-5 text-left text-white"
              >
                <span>
                  <span className="block text-[15px]">
                    {t.unidades} {t.unidades === 1 ? 'producto' : 'productos'} · {SERVICIO[carrito.tipoServicio]}
                  </span>
                  <span className="block text-[22px] leading-tight font-bold">{pesos(t.cobrar)}</span>
                </span>
                <span className="text-[19px] font-bold">Ver y cobrar</span>
              </button>
            </div>
          )}
          {hojaAbierta && <HojaVenta alCerrar={() => setHojaAbierta(false)}>{panel}</HojaVenta>}
        </>
      )}

      <DialogoLinea
        linea={linea}
        adiciones={productoLinea?.modificadores ?? []}
        alCerrar={() => setLineaEditada(null)}
        alGuardar={(cambios) => linea && setCarrito((c) => editarLinea(c, linea.id, cambios))}
        alQuitar={() => linea && setCarrito((c) => quitarLinea(c, linea.id))}
      />
      <DialogoDescuento
        abierto={editandoDescuento}
        alCerrar={() => setEditandoDescuento(false)}
        base={t.subtotal - t.descuentoItems}
        actual={carrito.descuento}
        alGuardar={(d) => setCarrito((c) => ({ ...c, descuento: d }))}
      />
      <DialogoPropina
        abierto={editandoPropina}
        alCerrar={() => setEditandoPropina(false)}
        actual={carrito.propina}
        alGuardar={(v) => setCarrito((c) => ({ ...c, propina: v }))}
      />
      <DialogoAutorizacion
        abierto={pidiendoAutorizacion}
        alCerrar={() => {
          setPidiendoAutorizacion(false)
          vender.reset()
        }}
        alAutorizar={(a) => vender.mutate(a)}
        ocupado={vender.isPending}
        error={vender.error instanceof ErrorApi && vender.error.codigo === 'AUTORIZACION_INVALIDA' ? vender.error.message : undefined}
      />
      <VentaRegistrada venta={registrada} alCerrar={() => setRegistrada(null)} />
    </div>
  )
}

/** Celular: el carrito ocupa toda la pantalla, con un botón para volver al catálogo. */
function HojaVenta({ alCerrar, children }: { alCerrar: () => void; children: React.ReactNode }) {
  const volver = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    volver.current?.focus()
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = ''
    }
  }, [])
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Venta actual"
      onKeyDown={(e) => e.key === 'Escape' && !e.defaultPrevented && alCerrar()}
      className="fixed inset-0 z-30 overflow-y-auto bg-blanco"
    >
      <div className="sticky top-0 z-10 border-b border-linea bg-blanco px-2 py-2">
        <button
          ref={volver}
          type="button"
          onClick={alCerrar}
          className="flex h-11 items-center gap-2 rounded-control px-3 text-[16px] font-semibold text-fucsia"
        >
          <ArrowLeft aria-hidden className="size-5" />
          Seguir agregando
        </button>
      </div>
      {children}
    </div>
  )
}

/** Sin caja abierta no se vende (RN-02): se abre aquí mismo si se tiene permiso. */
function CajaCerrada() {
  const { puede } = useSesion()
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const [base, setBase] = useState<number | null>(null)
  const abrir = useMutation({
    mutationFn: () => api('/caja/abrir', { method: 'POST', json: { base_inicial: base ?? 0 } }),
    onSuccess: () => {
      avisar('Caja abierta. ¡A vender!')
      void clienteQuery.invalidateQueries({ queryKey: ['caja'] })
    },
    onError: (e) => {
      avisar(e.message, 'error')
      void clienteQuery.invalidateQueries({ queryKey: ['caja'] })
    },
  })
  return (
    <div className="grid min-h-[70dvh] place-items-center px-4 py-10">
      <Tarjeta className="w-full max-w-[440px] p-7">
        <TituloTarjeta>La caja está cerrada</TituloTarjeta>
        {puede('caja.abrir') ? (
          <form
            className="mt-4 grid gap-4"
            onSubmit={(e) => {
              e.preventDefault()
              abrir.mutate()
            }}
          >
            <p className="text-cafe-medio">Para vender, primero abre la caja con el efectivo con el que arranca el turno.</p>
            <CampoDinero etiqueta="Base inicial en efectivo" valor={base} alCambiar={setBase} />
            <Boton type="submit" disabled={base === null || abrir.isPending}>
              Abrir caja
            </Boton>
          </form>
        ) : (
          <p className="mt-4 text-cafe-medio">
            Para vender hace falta una caja abierta. Pide a quien abre la caja que la abra
            {puede('caja.cerrar') || puede('caja.movimientos') ? (
              <>
                {' '}
                o ve a{' '}
                <Link to="/caja" className="font-semibold text-fucsia underline">
                  Caja
                </Link>
              </>
            ) : null}
            .
          </p>
        )}
      </Tarjeta>
    </div>
  )
}
