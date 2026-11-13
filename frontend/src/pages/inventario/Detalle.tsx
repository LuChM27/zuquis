import { useQuery } from '@tanstack/react-query'
import { useSesion } from '../../auth/contexto'
import { Aviso } from '../../components/formulario'
import { Boton } from '../../components/ui'
import { api } from '../../lib/api'
import { unir } from '../../lib/clases'
import { dec } from '../../lib/decimal'
import { ZONA } from '../../lib/formato'
import type { Lote, RecetaUso, StockItem } from '../../lib/tipos'
import { cantidadLegible, costoPorUnidad, fechaDiaMes } from '../../lib/unidades'
import { rutaItem } from './comun'

const diaMes = new Intl.DateTimeFormat('es-CO', { timeZone: ZONA, day: 'numeric', month: 'long' })

/** Contenido del panel de detalle: lotes en orden PEPS, recetas que lo usan y acciones. */
export function Detalle({
  item,
  hoy,
  alVerKardex,
  alMerma,
  alAjuste,
}: {
  item: StockItem
  hoy: string
  alVerKardex: () => void
  alMerma: () => void
  alAjuste: () => void
}) {
  const { puede } = useSesion()
  const lotes = useQuery({
    queryKey: ['inventario', 'lotes', item.item_id],
    queryFn: () => api<Lote[]>(`${rutaItem(item)}/lotes`),
  })
  const recetas = useQuery({
    queryKey: ['inventario', 'recetas', item.item_id],
    queryFn: () => api<RecetaUso[]>(`${rutaItem(item)}/recetas`),
    enabled: item.tipo_item === 'insumo',
  })
  const vigentes = (lotes.data ?? []).filter((l) => !l.vencido)
  const siguiente = vigentes[1]?.id

  return (
    <>
      {lotes.isError && <Aviso>No pudimos cargar los lotes. Recarga la página para intentarlo de nuevo.</Aviso>}
      {lotes.isSuccess && lotes.data.length === 0 && (
        <p className="rounded-control border border-linea p-4 text-cafe-medio">
          No hay existencias. Entran con una compra{item.tipo_item === 'producto' ? ' o una producción' : ''}.
        </p>
      )}
      <ol aria-label="Lotes en orden de uso" className="flex flex-col gap-3">
        {lotes.data?.map((l) => (
          <TarjetaLote key={l.id} lote={l} unidad={item.unidad} hoy={hoy} siguiente={l.id === siguiente} />
        ))}
      </ol>

      {item.tipo_item === 'insumo' && <Recetas cantidad={item.usado_en_recetas} usos={recetas.data} />}

      <div className="mt-5 flex flex-col gap-2.5">
        <Boton variante="secundario" onClick={alVerKardex}>
          Ver kardex
        </Boton>
        {puede('inventario.merma') && (
          <Boton variante="secundario" onClick={alMerma}>
            Registrar merma
          </Boton>
        )}
        {puede('inventario.ajustar') && (
          <Boton variante="secundario" onClick={alAjuste}>
            Ajustar por conteo
          </Boton>
        )}
      </div>
    </>
  )
}

function TarjetaLote({ lote, unidad, hoy, siguiente }: { lote: Lote; unidad: string; hoy: string; siguiente: boolean }) {
  const inicial = cantidadLegible(lote.cantidad_inicial, unidad)
  const costo = costoPorUnidad(lote.costo_unitario, unidad)
  const origen = {
    compra: `Compra de ${inicial} a ${costo}${lote.proveedor ? ` · ${lote.proveedor}` : ''}`,
    produccion: `Producción de ${inicial} a ${costo}`,
    ajuste: `Ajuste por conteo de ${inicial} a ${costo}`,
  }[lote.origen]
  const porcentaje = dec(lote.cantidad_disponible).div(dec(lote.cantidad_inicial)).mul(100).toDecimalPlaces(1).toFixed()
  const marca = lote.vencido
    ? { texto: 'Vencido', clase: 'text-peligro-texto' }
    : lote.se_usa_primero
      ? { texto: 'Se usa primero', clase: 'text-fucsia-oscuro' }
      : siguiente
        ? { texto: 'Siguiente', clase: 'text-cafe-medio' }
        : null

  return (
    <li
      className={unir(
        'rounded-tarjeta border px-5 py-4',
        lote.vencido ? 'border-peligro/25 bg-peligro-fila' : 'border-linea',
        lote.se_usa_primero && 'bg-crema',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 text-base font-semibold">Lote del {diaMes.format(new Date(lote.fecha_ingreso))}</p>
        {marca && <p className={unir('max-w-[45%] text-right text-sm font-semibold', marca.clase)}>{marca.texto}</p>}
      </div>
      <p className="mt-1.5 text-[15px] text-cafe-medio">
        {origen}
        {lote.fecha_vencimiento && (
          <>
            {' · '}
            {lote.vencido ? 'venció' : 'vence'} el {fechaDiaMes(lote.fecha_vencimiento, hoy)}
          </>
        )}
      </p>
      <div
        role="progressbar"
        aria-label="Lo que queda del lote"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Number(porcentaje)}
        className="mt-3 h-2 overflow-hidden rounded-full bg-pista"
      >
        <div className="h-full rounded-full bg-dorado" style={{ width: `${porcentaje}%` }} />
      </div>
      <p className="mt-2.5 text-[15px] text-cafe-medio">Quedan {cantidadLegible(lote.cantidad_disponible, unidad)}</p>
    </li>
  )
}

function Recetas({ cantidad, usos }: { cantidad: number; usos?: RecetaUso[] }) {
  const nombres = usos?.map((u) => u.nombre) ?? []
  const visibles = nombres.slice(0, 4)
  const resto = nombres.length - visibles.length
  return (
    <div className="mt-4 rounded-tarjeta bg-rosa-suave px-5 py-4">
      <p className="text-[17px] font-semibold">
        {cantidad === 0 ? 'No se usa en recetas' : `Se usa en ${cantidad} ${cantidad === 1 ? 'receta' : 'recetas'}`}
      </p>
      <p className="mt-1.5 text-[15px] text-cafe-medio">
        {cantidad === 0
          ? 'Solo sale con mermas, ajustes o ventas directas.'
          : `${visibles.map((n, i) => (i === 0 ? n : n.charAt(0).toLowerCase() + n.slice(1))).join(', ')}${resto > 0 ? ` y ${resto} más` : ''}. Cada venta o producción descuenta lo que gasta.`}
      </p>
    </div>
  )
}
