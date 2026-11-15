import { Interruptor } from '../../components/formulario'
import { useCaja } from './usarCaja'

/**
 * "Sale de la caja": el pago se descuenta del efectivo de la caja abierta (movimiento
 * pago_compra) y aparece en el cierre. Sin caja abierta no se puede marcar.
 */
export function SaleDeCaja({ activo, alCambiar }: { activo: boolean; alCambiar: (v: boolean) => void }) {
  const caja = useCaja()
  const abierta = caja.data?.abierta ?? false
  return (
    <Interruptor
      etiqueta="Sale de la caja"
      ayuda={abierta ? 'Se descuenta del dinero de la caja abierta y aparece en el cierre.' : 'No hay caja abierta: el pago no sale de la caja.'}
      activo={activo && abierta}
      alCambiar={alCambiar}
      deshabilitado={!abierta}
    />
  )
}
