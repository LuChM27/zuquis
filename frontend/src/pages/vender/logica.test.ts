import { agregar, carritoVacio } from '../../lib/carrito'
import type { MetodoPago, Producto } from '../../lib/tipos'
import { estadoProducto, motivoNoCobrar } from './logica'

const base: Producto = {
  id: 'p',
  categoria_id: 'c',
  nombre: 'Pastel de pollo',
  tipo: 'lote',
  precio: 4500,
  foto_url: null,
  disponible: true,
  activo: true,
  stock_minimo: '5.0000',
  dias_vida_util: 2,
  modificadores: [],
  tiene_receta: true,
  stock: '12.0000',
}

const metodos = [
  { id: 'ef', nombre: 'Efectivo', es_efectivo: true },
  { id: 'nq', nombre: 'Nequi', es_efectivo: false },
] as MetodoPago[]

describe('estado de la tarjeta de producto', () => {
  it('muestra las unidades en vitrina en verde, o en rojo en el mínimo', () => {
    expect(estadoProducto(base)).toEqual({ texto: '12 en vitrina', tono: 'bien', vendible: true })
    expect(estadoProducto({ ...base, stock: '3.0000' }).tono).toBe('bajo')
  })

  it('un preparado sin receta o un producto agotado no se puede vender', () => {
    expect(estadoProducto({ ...base, tipo: 'preparado' }).texto).toBe('Se prepara')
    expect(estadoProducto({ ...base, tipo: 'preparado', tiene_receta: false }).vendible).toBe(false)
    expect(estadoProducto({ ...base, disponible: false }).vendible).toBe(false)
  })
})

describe('qué falta para cobrar', () => {
  const carrito = agregar(carritoVacio(), { id: 'p', nombre: 'Pastel', precio: 4500 })

  it('pide productos y método de pago', () => {
    expect(motivoNoCobrar(carritoVacio(), { elegidos: [], recibido: null }, metodos)).toBe('Agrega productos a la venta.')
    expect(motivoNoCobrar(carrito, { elegidos: [], recibido: null }, metodos)).toBe('Elige cómo paga.')
    expect(motivoNoCobrar(carrito, { elegidos: [{ metodoId: 'ef', monto: null }], recibido: null }, metodos)).toBeNull()
  })

  it('en pago mixto, cada método debe llevar monto y el primero algo de saldo', () => {
    const sinMonto = { elegidos: [{ metodoId: 'ef', monto: null }, { metodoId: 'nq', monto: 0 }], recibido: null }
    expect(motivoNoCobrar(carrito, sinMonto, metodos)).toBe('Escribe cuánto paga con cada método.')
    const todo = { elegidos: [{ metodoId: 'ef', monto: null }, { metodoId: 'nq', monto: 4500 }], recibido: null }
    expect(motivoNoCobrar(carrito, todo, metodos)).toMatch(/ya cubren todo/)
  })

  it('lo recibido en efectivo debe alcanzar', () => {
    const corto = { elegidos: [{ metodoId: 'ef', monto: null }], recibido: 2000 }
    expect(motivoNoCobrar(carrito, corto, metodos)).toBe('Lo recibido en efectivo no alcanza.')
  })

  it('una cortesía de $0 se registra sin pagos', () => {
    const cortesia = { ...carrito, descuento: { tipo: 'porcentaje' as const, valor: '100', motivo: 'Cortesía' } }
    expect(motivoNoCobrar(cortesia, { elegidos: [], recibido: null }, metodos)).toBeNull()
  })
})

describe('venta a domicilio', () => {
  const carrito = agregar(carritoVacio('domicilio'), { id: 'p', nombre: 'Pastel', precio: 4500, tipo: 'lote' } as never)
  const pago = { elegidos: [{ metodoId: 'ef', monto: null }], recibido: null }

  it('exige domiciliario y dirección', () => {
    expect(motivoNoCobrar(carrito, pago, metodos)).toBe('Elige quién lleva el domicilio.')
    const conDomiciliario = { ...carrito, entrega: { ...carrito.entrega, domiciliarioId: 'dom' } }
    expect(motivoNoCobrar(conDomiciliario, pago, metodos)).toBe('Escribe la dirección de entrega.')
    const completo = { ...conDomiciliario, entrega: { ...conDomiciliario.entrega, direccion: 'Cra 10' } }
    expect(motivoNoCobrar(completo, pago, metodos)).toBeNull()
  })
})
