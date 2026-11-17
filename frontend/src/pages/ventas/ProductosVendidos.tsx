import { Celda, Tabla } from '../../components/formulario'
import { cantidad } from '../../lib/decimal'
import { pesos } from '../../lib/formato'
import type { ResumenVentas } from '../../lib/tipos'

/** "Lo que se vendió" en el día. Las líneas sin producto (personalizados, decoración) se agrupan
 * por su descripción, así que la clave es producto + nombre. */
export function ProductosVendidos({ productos }: { productos: ResumenVentas['productos'] }) {
  return (
    <Tabla columnas={[{ texto: 'Producto' }, { texto: 'Cantidad', derecha: true }, { texto: 'Valor', derecha: true }]}>
      {productos.map((p) => (
        <tr key={`${p.producto_id ?? 'sin-producto'}:${p.producto}`} className="border-b border-linea last:border-b-0">
          <Celda className="font-medium">{p.producto}</Celda>
          <Celda derecha>{cantidad(p.cantidad)}</Celda>
          <Celda derecha className="font-semibold">
            {pesos(p.valor)}
          </Celda>
        </tr>
      ))}
    </Tabla>
  )
}
