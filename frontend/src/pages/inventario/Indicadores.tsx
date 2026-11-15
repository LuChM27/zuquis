import type { ReactNode } from 'react'
import { pesos } from '../../lib/formato'
import { unir } from '../../lib/clases'
import type { ResumenInventario } from '../../lib/tipos'
import { listaNatural, lotesPorItem } from './comun'

/** Las 4 tarjetas de cifras del mockup: valor, bajo el mínimo, por vencer y mermas del mes. */
export function Indicadores({ resumen }: { resumen?: ResumenInventario }) {
  const r = resumen
  const bajos = r?.bajo_minimo.length ?? 0
  return (
    <div className="mb-[22px] grid grid-cols-2 gap-2.5 sm:gap-4 xl:grid-cols-4">
      <Cifra titulo="Valor del inventario" valor={r ? pesos(r.valor_inventario) : '—'} detalle="A costo de compra de cada lote" />
      <Cifra
        tono={bajos > 0 ? 'peligro' : undefined}
        titulo="Bajo el mínimo"
        valor={r ? `${bajos} ${bajos === 1 ? 'insumo' : 'insumos'}` : '—'}
        detalle={bajos > 0 ? listaNatural(r!.bajo_minimo) : 'Todo está por encima del mínimo'}
      />
      <Cifra
        tono={(r?.lotes_por_vencer ?? 0) > 0 ? 'aviso' : undefined}
        titulo={`Vencen en ${r?.dias_alerta_vencimiento ?? 3} días o menos`}
        valor={r ? `${r.lotes_por_vencer} ${r.lotes_por_vencer === 1 ? 'lote' : 'lotes'}` : '—'}
        detalle={r && r.lotes_por_vencer > 0 ? lotesPorItem(r.por_vencer) : 'Nada vence pronto'}
      />
      <Cifra titulo="Mermas del mes" valor={r ? pesos(r.mermas_mes) : '—'} detalle="Vencidos, dañados y degustaciones" />
    </div>
  )
}

export function Cifra({
  titulo,
  valor,
  detalle,
  tono,
}: {
  titulo: string
  valor: string
  detalle: ReactNode
  tono?: 'peligro' | 'aviso'
}) {
  return (
    <section
      className={unir(
        'min-w-0 rounded-tarjeta border px-4 py-4 sm:px-6 sm:py-5',
        tono === 'peligro' && 'border-peligro/25 bg-peligro-fondo',
        tono === 'aviso' && 'border-aviso/25 bg-aviso-fondo',
        !tono && 'border-dorado-claro bg-blanco',
      )}
    >
      <h2
        className={unir(
          'text-sm font-medium sm:text-[15px]',
          tono === 'peligro' ? 'text-peligro-texto' : tono === 'aviso' ? 'text-aviso-texto' : 'text-cafe-medio',
        )}
      >
        {titulo}
      </h2>
      <p
        className={unir(
          'mt-2 font-serif text-[30px] leading-none font-semibold [font-variant-numeric:oldstyle-nums] sm:text-[40px]',
          tono === 'peligro' && 'text-peligro-texto',
          tono === 'aviso' && 'text-aviso-texto',
        )}
      >
        {valor}
      </p>
      <p className="mt-2.5 text-[13px] leading-snug text-cafe-medio sm:mt-3 sm:text-sm">{detalle}</p>
    </section>
  )
}
