import { useMutation } from '@tanstack/react-query'
import { useAvisos } from '../../components/usarAvisos'
import { apiBlob, ErrorApi } from '../../lib/api'
import { pesos } from '../../lib/formato'
import type { Venta } from '../../lib/tipos'

export function textoComprobante(v: Venta): string {
  const lineas = v.items.map((i) => `${Number(i.cantidad)} × ${i.producto}: ${pesos(i.subtotal)}`)
  return [
    `Zuqui's Repostería · Venta n.º ${String(v.numero).padStart(4, '0')}`,
    ...lineas,
    v.descuento_total ? `Descuento: −${pesos(v.descuento_total)}` : null,
    `Total: ${pesos(v.total)}`,
    v.propina ? `Propina: ${pesos(v.propina)}` : null,
    v.valor_domicilio ? `Domicilio: ${pesos(v.valor_domicilio)}` : null,
    v.abonos_aplicados ? `Abonos ya recibidos: −${pesos(v.abonos_aplicados)}` : null,
    v.abonos_aplicados ? `Pagado hoy: ${pesos(v.cobrado)}` : null,
    '¡Gracias por tu compra!',
  ]
    .filter(Boolean)
    .join('\n')
}

/** Imprimir el comprobante en PDF o compartirlo (WhatsApp en el celular). */
export function useComprobante(venta: Venta | null) {
  const { avisar } = useAvisos()
  const pdf = useMutation({
    mutationFn: async () => apiBlob(`/ventas/${venta!.id}/comprobante`),
    onError: (e) => avisar(e instanceof ErrorApi ? e.message : 'No se pudo generar el comprobante.', 'error'),
  })

  async function imprimir() {
    const blob = await pdf.mutateAsync().catch(() => null)
    if (!blob) return
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  }

  async function compartir() {
    const v = venta!
    const texto = textoComprobante(v)
    const blob = await pdf.mutateAsync().catch(() => null)
    const archivo = blob ? new File([blob], `venta-${v.numero}.pdf`, { type: 'application/pdf' }) : null
    // En el celular se comparte el PDF (WhatsApp lo ofrece); si no se puede, va el texto.
    if (archivo && navigator.canShare?.({ files: [archivo] })) {
      try {
        await navigator.share({ files: [archivo], text: texto })
      } catch {
        // Se canceló el menú de compartir.
      }
      return
    }
    window.open(`https://wa.me/?text=${encodeURIComponent(texto)}`, '_blank', 'noopener')
  }

  return { imprimir, compartir, ocupado: pdf.isPending }
}
