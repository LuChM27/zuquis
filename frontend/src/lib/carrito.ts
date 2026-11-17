/**
 * Carrito del punto de venta: estado local (agregar responde sin esperar a la red, RNF-03) y
 * los mismos cálculos que el backend (backend/app/modules/ventas/service.py), en pesos enteros
 * y con decimal.js para los porcentajes:
 *
 *   bruto de la línea = precio × cantidad + Σ (precio de la adición × cantidad)
 *   descuento de la venta = sobre (subtotal − descuentos de los ítems)
 *   total = subtotal − descuentos;  a cobrar = total + propina + domicilio
 */
import type { DescuentoEntrada, TipoServicio } from './tipos'
import { aPesos, dec } from './decimal'

export interface ProductoCarrito {
  id: string
  nombre: string
  precio: number
}

export interface AdicionCarrito {
  id: string
  nombre: string
  precio: number
}

export interface LineaCarrito {
  /** Identificador local de la línea (un producto puede ir en dos líneas con adiciones distintas). */
  id: string
  producto: ProductoCarrito
  cantidad: number
  adiciones: AdicionCarrito[]
  nota: string
  descuento: DescuentoEntrada | null
}

/** A quién se le vende y, si es a domicilio, quién lo lleva y a dónde (RF-13). */
export interface DatosEntrega {
  clienteId: string
  domiciliarioId: string
  direccion: string
  telefono: string
}

export interface Carrito {
  tipoServicio: TipoServicio
  lineas: LineaCarrito[]
  descuento: DescuentoEntrada | null
  propina: number
  valorDomicilio: number
  entrega: DatosEntrega
}

export const entregaVacia = (): DatosEntrega => ({ clienteId: '', domiciliarioId: '', direccion: '', telefono: '' })

export function carritoVacio(tipoServicio: TipoServicio = 'local'): Carrito {
  return { tipoServicio, lineas: [], descuento: null, propina: 0, valorDomicilio: 0, entrega: entregaVacia() }
}

let consecutivoLinea = 0
const nuevoId = () => `l${++consecutivoLinea}`

const esSimple = (l: LineaCarrito) => l.adiciones.length === 0 && !l.nota && !l.descuento

/** Suma una unidad: a la línea simple del mismo producto si existe, o en una línea nueva. */
export function agregar(c: Carrito, producto: ProductoCarrito): Carrito {
  const existente = c.lineas.find((l) => l.producto.id === producto.id && esSimple(l))
  if (existente) return cambiarCantidad(c, existente.id, 1)
  const linea: LineaCarrito = { id: nuevoId(), producto, cantidad: 1, adiciones: [], nota: '', descuento: null }
  return { ...c, lineas: [...c.lineas, linea] }
}

/** Suma o resta unidades; en cero la línea sale del carrito. */
export function cambiarCantidad(c: Carrito, lineaId: string, delta: number): Carrito {
  const lineas = c.lineas
    .map((l) => (l.id === lineaId ? { ...l, cantidad: l.cantidad + delta } : l))
    .filter((l) => l.cantidad > 0)
  return { ...c, lineas }
}

export function editarLinea(c: Carrito, lineaId: string, cambios: Partial<Omit<LineaCarrito, 'id'>>): Carrito {
  return { ...c, lineas: c.lineas.map((l) => (l.id === lineaId ? { ...l, ...cambios } : l)) }
}

/** Regalo: descuento del 100 % del producto con motivo "Regalo" (la venta sigue descontando inventario). */
export const REGALO: DescuentoEntrada = { tipo: 'porcentaje', valor: '100', motivo: 'Regalo' }

export function esRegalo(l: LineaCarrito): boolean {
  return l.descuento?.tipo === 'porcentaje' && Number(l.descuento.valor) === 100
}

export function alternarRegalo(c: Carrito, lineaId: string): Carrito {
  return {
    ...c,
    lineas: c.lineas.map((l) => (l.id === lineaId ? { ...l, descuento: esRegalo(l) ? null : REGALO } : l)),
  }
}

export function quitarLinea(c: Carrito, lineaId: string): Carrito {
  return { ...c, lineas: c.lineas.filter((l) => l.id !== lineaId) }
}

/** Pesos que descuenta sobre `base` (redondeo a peso, mitad hacia arriba). */
export function montoDescuento(base: number, d: DescuentoEntrada | null): number {
  if (!d) return 0
  if (d.tipo === 'porcentaje') return aPesos(dec(String(base)).mul(dec(d.valor)).div(100))
  return aPesos(dec(d.valor))
}

export interface TotalesLinea {
  id: string
  bruto: number
  descuento: number
  neto: number
}

export interface Totales {
  lineas: TotalesLinea[]
  subtotal: number
  descuentoItems: number
  descuentoVenta: number
  descuentoTotal: number
  total: number
  propina: number
  domicilio: number
  cobrar: number
  unidades: number
  /** Algún descuento es mayor que el valor al que se aplica. */
  descuentoExcedido: boolean
}

export function calcular(c: Carrito): Totales {
  const lineas = c.lineas.map((l) => {
    const bruto = l.producto.precio * l.cantidad + l.adiciones.reduce((s, a) => s + a.precio * l.cantidad, 0)
    const descuento = montoDescuento(bruto, l.descuento)
    return { id: l.id, bruto, descuento, neto: bruto - descuento }
  })
  const subtotal = lineas.reduce((s, l) => s + l.bruto, 0)
  const descuentoItems = lineas.reduce((s, l) => s + l.descuento, 0)
  const descuentoVenta = montoDescuento(subtotal - descuentoItems, c.descuento)
  const descuentoTotal = descuentoItems + descuentoVenta
  const total = subtotal - descuentoTotal
  const domicilio = c.tipoServicio === 'domicilio' ? c.valorDomicilio : 0
  return {
    lineas,
    subtotal,
    descuentoItems,
    descuentoVenta,
    descuentoTotal,
    total,
    propina: c.propina,
    domicilio,
    cobrar: total + c.propina + domicilio,
    unidades: c.lineas.reduce((s, l) => s + l.cantidad, 0),
    descuentoExcedido: lineas.some((l) => l.descuento > l.bruto) || descuentoVenta > subtotal - descuentoItems,
  }
}

export interface PagoElegido {
  metodoId: string
  /** null en el primer método: recibe lo que falte. */
  monto: number | null
}

/** Pago mixto: los métodos que siguen al primero llevan su monto; el primero cubre el resto. */
export function pagosPara(cobrar: number, elegidos: PagoElegido[]): { metodoId: string; monto: number }[] {
  if (elegidos.length === 0) return []
  const [primero, ...resto] = elegidos
  const otros = resto.map((p) => ({ metodoId: p.metodoId, monto: p.monto ?? 0 }))
  const suma = otros.reduce((s, p) => s + p.monto, 0)
  return [{ metodoId: primero.metodoId, monto: cobrar - suma }, ...otros]
}

/** Cuerpo de POST /ventas. */
export function cuerpoVenta(
  c: Carrito,
  pagos: { metodoId: string; monto: number; recibido?: number | null }[],
): Record<string, unknown> {
  const aDomicilio = c.tipoServicio === 'domicilio'
  return {
    tipo_servicio: c.tipoServicio,
    cliente_id: c.entrega.clienteId || null,
    domicilio: aDomicilio
      ? {
          domiciliario_id: c.entrega.domiciliarioId,
          direccion: c.entrega.direccion.trim(),
          telefono: c.entrega.telefono.trim() || null,
        }
      : null,
    items: c.lineas.map((l) => ({
      producto_id: l.producto.id,
      cantidad: String(l.cantidad),
      modificador_ids: l.adiciones.map((a) => a.id),
      nota: l.nota.trim() || null,
      descuento: l.descuento,
    })),
    descuento: c.descuento,
    propina: c.propina,
    valor_domicilio: aDomicilio ? c.valorDomicilio : 0,
    pagos: pagos
      .filter((p) => p.monto > 0)
      .map((p) => ({ metodo_pago_id: p.metodoId, monto: p.monto, recibido: p.recibido ?? null })),
  }
}
