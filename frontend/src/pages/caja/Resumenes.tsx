import { unir } from '../../lib/clases'
import { pesos } from '../../lib/formato'
import type { ResumenTurno } from '../../lib/tipos'

const fila = 'flex items-baseline justify-between gap-4 py-2'

/** "De dónde sale el efectivo": base, entradas en verde-neutro con +, salidas en rojo. */
export function DeDondeSaleElEfectivo({ lineas, total }: { lineas: { concepto: string; monto: number }[]; total: number }) {
  return (
    <dl>
      {lineas.map((l, i) => (
        <div key={l.concepto} className={fila}>
          <dt className="text-cafe-medio">{l.concepto}</dt>
          <dd className={unir('font-semibold', l.monto < 0 && 'text-peligro-texto')}>
            {i === 0 ? pesos(l.monto) : pesos(l.monto, { signo: true })}
          </dd>
        </div>
      ))}
      <div className={unir(fila, 'mt-2 border-t border-dorado-claro pt-3')}>
        <dt className="text-[19px] font-bold">Debería haber en efectivo</dt>
        <dd className="text-[19px] font-bold">{pesos(total)}</dd>
      </div>
    </dl>
  )
}

export function ResumenDelTurno({ resumen }: { resumen: ResumenTurno }) {
  const lineas: [string, number, boolean][] = [
    ['Ventas del turno', resumen.ventas, true],
    ['Abonos recibidos (cuentan como venta al entregar)', resumen.abonos, true],
    ['Propinas (dinero de terceros)', resumen.propinas, true],
    ['Gastos pagados de la caja', resumen.gastos, true],
    ['Domicilios entregados al domiciliario', resumen.domicilios_entregados, true],
    ['Pagos a proveedores desde la caja', resumen.pagos_proveedores, false],
    ['Anulaciones devueltas', resumen.anulaciones, false],
  ]
  return (
    <dl>
      {lineas
        .filter(([, monto, siempre]) => siempre || monto !== 0)
        .map(([texto, monto]) => (
          <div key={texto} className={fila}>
            <dt className="text-cafe-medio">{texto}</dt>
            <dd className="font-semibold">{pesos(monto)}</dd>
          </div>
        ))}
    </dl>
  )
}
