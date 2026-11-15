import { agregar, alternarRegalo, calcular, cambiarCantidad, carritoVacio, esRegalo, pagosPara, type Carrito, type ProductoCarrito } from './carrito'

const malteada: ProductoCarrito = { id: 'malteada', nombre: 'Malteada de brownie', precio: 16000 }
const soda: ProductoCarrito = { id: 'soda', nombre: 'Soda frutos rojos', precio: 12000 }
const pastel: ProductoCarrito = { id: 'pastel', nombre: 'Pastel de pollo', precio: 4500 }
const croissant: ProductoCarrito = { id: 'croissant', nombre: 'Croissant de jamón y queso', precio: 7500 }
const helado = { id: 'helado', nombre: 'Bola de helado', precio: 5000 }

/** La venta del mockup del punto de venta (pos-escritorio.png). */
function ventaMockup(): Carrito {
  let c = carritoVacio()
  c = agregar(c, malteada)
  c = { ...c, lineas: c.lineas.map((l) => ({ ...l, adiciones: [helado] })) }
  c = agregar(c, soda)
  c = { ...c, lineas: c.lineas.map((l) => (l.producto.id === 'soda' ? { ...l, nota: 'Sin hielo' } : l)) }
  c = agregar(agregar(c, pastel), pastel)
  c = agregar(c, croissant)
  return {
    ...c,
    descuento: { tipo: 'valor', valor: '3000', motivo: 'Cliente frecuente' },
    propina: 2000,
  }
}

describe('carrito del punto de venta', () => {
  it('reproduce los totales del mockup al peso', () => {
    const t = calcular(ventaMockup())
    expect(t.lineas.map((l) => l.bruto)).toEqual([21000, 12000, 9000, 7500])
    expect(t.subtotal).toBe(49500)
    expect(t.descuentoTotal).toBe(3000)
    expect(t.total).toBe(46500)
    expect(t.cobrar).toBe(48500)
    expect(t.unidades).toBe(5)
  })

  it('agregar el mismo producto sin adiciones suma una unidad a su línea', () => {
    const c = agregar(agregar(carritoVacio(), pastel), pastel)
    expect(c.lineas).toHaveLength(1)
    expect(c.lineas[0].cantidad).toBe(2)
  })

  it('un producto con adiciones o nota no se mezcla con uno nuevo igual', () => {
    const c = agregar(ventaMockup(), malteada)
    expect(c.lineas.filter((l) => l.producto.id === 'malteada')).toHaveLength(2)
  })

  it('bajar a cero quita la línea', () => {
    const c = agregar(carritoVacio(), pastel)
    expect(cambiarCantidad(c, c.lineas[0].id, -1).lineas).toHaveLength(0)
  })

  it('descuento por porcentaje se redondea a peso como el backend', () => {
    const c = { ...agregar(carritoVacio(), pastel), descuento: { tipo: 'porcentaje' as const, valor: '33.3333', motivo: 'Prueba' } }
    expect(calcular(c).descuentoTotal).toBe(1500)
  })

  it('el descuento de la venta se aplica después del de cada ítem', () => {
    let c = agregar(carritoVacio(), malteada)
    c = { ...c, lineas: [{ ...c.lineas[0], descuento: { tipo: 'valor', valor: '1000', motivo: 'Prueba' } }] }
    c = { ...c, descuento: { tipo: 'porcentaje', valor: '10', motivo: 'Prueba' } }
    const t = calcular(c)
    expect(t.lineas[0].descuento).toBe(1000)
    expect(t.descuentoVenta).toBe(1500)
    expect(t.total).toBe(13500)
  })

  it('el domicilio solo se cobra en ventas a domicilio', () => {
    const c = { ...agregar(carritoVacio(), pastel), valorDomicilio: 5000 }
    expect(calcular(c).cobrar).toBe(4500)
    expect(calcular({ ...c, tipoServicio: 'domicilio' }).cobrar).toBe(9500)
  })
})

describe('pago mixto', () => {
  it('con un solo método, ese método paga todo', () => {
    expect(pagosPara(48500, [{ metodoId: 'efectivo', monto: null }])).toEqual([{ metodoId: 'efectivo', monto: 48500 }])
  })

  it('el primer método recibe lo que falta después de los demás', () => {
    const pagos = pagosPara(48500, [
      { metodoId: 'efectivo', monto: null },
      { metodoId: 'nequi', monto: 20000 },
    ])
    expect(pagos).toEqual([
      { metodoId: 'efectivo', monto: 28500 },
      { metodoId: 'nequi', monto: 20000 },
    ])
  })

  it('si los demás pagan todo o más, el primero queda en cero o negativo para avisar', () => {
    const pagos = pagosPara(10000, [
      { metodoId: 'efectivo', monto: null },
      { metodoId: 'nequi', monto: 12000 },
    ])
    expect(pagos[0].monto).toBe(-2000)
  })
})

describe('regalo', () => {
  it('marcar un producto como regalo lo deja en $0 con motivo, y desmarcarlo lo devuelve', () => {
    let c = agregar(agregar(carritoVacio(), pastel), malteada)
    const id = c.lineas[0].id
    c = alternarRegalo(c, id)
    expect(esRegalo(c.lineas[0])).toBe(true)
    expect(c.lineas[0].descuento).toEqual({ tipo: 'porcentaje', valor: '100', motivo: 'Regalo' })
    expect(calcular(c).total).toBe(16000)
    c = alternarRegalo(c, id)
    expect(esRegalo(c.lineas[0])).toBe(false)
    expect(calcular(c).total).toBe(20500)
  })

  it('un regalo no se mezcla con un producto igual que sí se cobra', () => {
    let c = agregar(carritoVacio(), pastel)
    c = alternarRegalo(c, c.lineas[0].id)
    c = agregar(c, pastel)
    expect(c.lineas).toHaveLength(2)
  })
})
