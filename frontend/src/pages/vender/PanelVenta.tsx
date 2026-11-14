import { Minus, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { CampoDinero } from '../../components/CampoDinero'
import { calcular, pagosPara, type Carrito } from '../../lib/carrito'
import { unir } from '../../lib/clases'
import { hora, pesos } from '../../lib/formato'
import type { MetodoPago, TipoServicio } from '../../lib/tipos'
import { motivoNoCobrar, type Cobro } from './logica'

const SERVICIOS: { valor: TipoServicio; texto: string }[] = [
  { valor: 'local', texto: 'En local' },
  { valor: 'llevar', texto: 'Para llevar' },
  { valor: 'domicilio', texto: 'Domicilio' },
]

/** Reloj de la cabecera ("5:42 p. m."), al minuto. */
function useHora(): string {
  const [ahora, setAhora] = useState(() => new Date())
  useEffect(() => {
    const t = setInterval(() => setAhora(new Date()), 15_000)
    return () => clearInterval(t)
  }, [])
  return hora(ahora)
}

export function PanelVenta({
  numero,
  carrito,
  alCambiar,
  cobro,
  alCambiarCobro,
  metodos,
  alEditarLinea,
  alDescuento,
  alPropina,
  alCobrar,
  cobrando,
}: {
  numero: number | undefined
  carrito: Carrito
  alCambiar: (c: Carrito) => void
  cobro: Cobro
  alCambiarCobro: (c: Cobro) => void
  metodos: MetodoPago[]
  alEditarLinea: (lineaId: string) => void
  alDescuento: () => void
  alPropina: () => void
  alCobrar: () => void
  cobrando: boolean
}) {
  const reloj = useHora()
  const t = calcular(carrito)
  const pagos = pagosPara(t.cobrar, cobro.elegidos)
  const montoDe = new Map(pagos.map((p) => [p.metodoId, p.monto]))
  const metodoEfectivo = metodos.find((m) => m.es_efectivo && montoDe.has(m.id))
  const efectivo = metodoEfectivo ? (montoDe.get(metodoEfectivo.id) ?? 0) : 0
  const cambio = cobro.recibido !== null && efectivo > 0 ? cobro.recibido - efectivo : null
  const bloqueo = motivoNoCobrar(carrito, cobro, metodos)

  function alternarMetodo(id: string) {
    const ya = cobro.elegidos.some((e) => e.metodoId === id)
    let elegidos = ya
      ? cobro.elegidos.filter((e) => e.metodoId !== id)
      : [...cobro.elegidos, { metodoId: id, monto: cobro.elegidos.length === 0 ? null : 0 }]
    // El primero siempre recibe lo que falta.
    elegidos = elegidos.map((e, i) => (i === 0 ? { ...e, monto: null } : e))
    const sigueEfectivo = elegidos.some((e) => metodos.find((m) => m.id === e.metodoId)?.es_efectivo)
    alCambiarCobro({ elegidos, recibido: sigueEfectivo ? cobro.recibido : null })
  }

  function montoOtro(id: string, monto: number | null) {
    alCambiarCobro({ ...cobro, elegidos: cobro.elegidos.map((e) => (e.metodoId === id ? { ...e, monto: monto ?? 0 } : e)) })
  }

  const fila = 'flex items-baseline justify-between gap-3'
  return (
    <div className="flex min-h-full flex-col px-5 pt-6 pb-5 lg:px-[34px] lg:pt-[42px] lg:pb-[30px]">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-serif text-[34px] leading-none font-medium">
          Venta n.º {numero !== undefined ? String(numero).padStart(4, '0') : '—'}
        </h2>
        <span className="text-[15px] text-cafe-suave">{reloj}</span>
      </div>

      <div role="radiogroup" aria-label="Tipo de servicio" className="mt-6 grid grid-cols-3 gap-1 rounded-[14px] bg-rosa-suave p-1">
        {SERVICIOS.map((s) => (
          <button
            key={s.valor}
            type="button"
            role="radio"
            aria-checked={carrito.tipoServicio === s.valor}
            onClick={() => alCambiar({ ...carrito, tipoServicio: s.valor })}
            className={unir(
              'h-[52px] rounded-[11px] text-[16px] transition-colors',
              carrito.tipoServicio === s.valor ? 'border border-dorado-borde bg-blanco font-semibold' : 'text-cafe hover:bg-blanco/50',
            )}
          >
            {s.texto}
          </button>
        ))}
      </div>

      {carrito.tipoServicio === 'domicilio' && (
        <CampoDinero
          className="mt-4"
          etiqueta="Valor del domicilio"
          valor={carrito.valorDomicilio || null}
          alCambiar={(v) => alCambiar({ ...carrito, valorDomicilio: v ?? 0 })}
        />
      )}

      {carrito.lineas.length === 0 ? (
        <p className="py-10 text-center text-cafe-medio">Toca un producto para agregarlo a la venta.</p>
      ) : (
        <ul aria-label="Productos de la venta" className="mt-3">
          {carrito.lineas.map((l, i) => {
            const tl = t.lineas[i]
            const detalle = [...l.adiciones.map((a) => `+ ${a.nombre}`), l.nota].filter(Boolean).join(' · ')
            return (
              <li key={l.id} aria-label={l.producto.nombre} className="flex items-center gap-3 border-b border-linea py-4">
                <button type="button" onClick={() => alEditarLinea(l.id)} className="min-w-0 flex-1 text-left" title="Adiciones, nota o descuento">
                  <span className="block text-[16px] leading-snug font-semibold [overflow-wrap:anywhere]">{l.producto.nombre}</span>
                  {detalle && <span className="mt-0.5 block text-sm text-cafe-suave">{detalle}</span>}
                  {tl.descuento > 0 && <span className="mt-0.5 block text-sm text-peligro-texto">Descuento −{pesos(tl.descuento)}</span>}
                </button>
                <div className="flex shrink-0 items-center gap-2">
                  <button
                    type="button"
                    aria-label={`Quitar una unidad de ${l.producto.nombre}`}
                    onClick={() => alCambiar({ ...carrito, lineas: carrito.lineas.map((x) => (x.id === l.id ? { ...x, cantidad: x.cantidad - 1 } : x)).filter((x) => x.cantidad > 0) })}
                    className="grid size-11 place-items-center rounded-control border border-dorado-claro bg-crema hover:border-dorado-borde"
                  >
                    <Minus aria-hidden className="size-4" strokeWidth={1.8} />
                  </button>
                  <span className="w-6 text-center text-[17px] font-semibold" aria-label={`Cantidad: ${l.cantidad}`}>
                    {l.cantidad}
                  </span>
                  <button
                    type="button"
                    aria-label={`Agregar una unidad de ${l.producto.nombre}`}
                    onClick={() => alCambiar({ ...carrito, lineas: carrito.lineas.map((x) => (x.id === l.id ? { ...x, cantidad: x.cantidad + 1 } : x)) })}
                    className="grid size-11 place-items-center rounded-control border border-dorado-claro bg-crema hover:border-dorado-borde"
                  >
                    <Plus aria-hidden className="size-4" strokeWidth={1.8} />
                  </button>
                </div>
                <span className="w-[76px] shrink-0 text-right text-[17px] font-semibold">{pesos(tl.neto)}</span>
              </li>
            )
          })}
        </ul>
      )}

      <div className="mt-4 flex gap-4 text-[15px] font-semibold text-fucsia">
        <button type="button" onClick={alDescuento} disabled={carrito.lineas.length === 0} className="hover:underline disabled:opacity-50">
          {carrito.descuento ? 'Cambiar descuento' : 'Agregar descuento'}
        </button>
        <button type="button" onClick={alPropina} disabled={carrito.lineas.length === 0} className="hover:underline disabled:opacity-50">
          {t.propina ? 'Cambiar propina' : 'Agregar propina'}
        </button>
      </div>

      <dl className="mt-4 grid gap-2.5 border-b border-linea pb-4 text-[16px]">
        <div className={fila}>
          <dt>Subtotal</dt>
          <dd>{pesos(t.subtotal)}</dd>
        </div>
        {t.descuentoTotal > 0 && (
          <div className={fila}>
            <dt className="min-w-0 truncate">Descuento{carrito.descuento ? ` · ${carrito.descuento.motivo.toLowerCase()}` : ''}</dt>
            <dd className="text-fucsia">−{pesos(t.descuentoTotal)}</dd>
          </div>
        )}
        <div className={fila}>
          <dt className="font-semibold">Total de la venta</dt>
          <dd className="font-semibold">{pesos(t.total)}</dd>
        </div>
        {t.propina > 0 && (
          <div className={unir(fila, 'text-cafe-suave')}>
            <dt>Propina (aparte, no es venta)</dt>
            <dd>{pesos(t.propina)}</dd>
          </div>
        )}
        {t.domicilio > 0 && (
          <div className={unir(fila, 'text-cafe-suave')}>
            <dt>Domicilio</dt>
            <dd>{pesos(t.domicilio)}</dd>
          </div>
        )}
      </dl>

      <div className="mt-5 flex items-center justify-between gap-3">
        <p className="text-[17px] font-semibold">Total a cobrar</p>
        <p className="font-serif text-[48px] leading-none font-semibold" aria-live="polite">
          {pesos(t.cobrar)}
        </p>
      </div>

      {t.cobrar > 0 && (
        <fieldset className="mt-5">
          <legend className="text-[16px] font-semibold">Cómo paga</legend>
          <div className="mt-3 grid grid-cols-2 gap-2.5">
            {metodos.map((m) => {
              const elegido = montoDe.has(m.id)
              const monto = montoDe.get(m.id) ?? 0
              return (
                <button
                  key={m.id}
                  type="button"
                  aria-pressed={elegido}
                  onClick={() => alternarMetodo(m.id)}
                  className={unir(
                    'h-[58px] rounded-control border px-2 text-[16px] transition-colors',
                    elegido ? 'border-2 border-fucsia bg-rosa-suave font-semibold' : 'border-dorado-claro bg-blanco hover:border-dorado-borde',
                  )}
                >
                  {m.nombre}
                  {elegido && monto > 0 && ` ${pesos(monto)}`}
                </button>
              )
            })}
          </div>
          {cobro.elegidos.length > 1 && (
            <div className="mt-3 grid gap-2.5">
              {cobro.elegidos.slice(1).map((e) => {
                const m = metodos.find((x) => x.id === e.metodoId)
                return (
                  <CampoDinero
                    key={e.metodoId}
                    etiqueta={`¿Cuánto paga con ${m?.nombre ?? 'este método'}?`}
                    valor={e.monto || null}
                    alCambiar={(v) => montoOtro(e.metodoId, v)}
                  />
                )
              })}
              <p className="text-sm text-cafe-suave">
                {metodos.find((m) => m.id === cobro.elegidos[0].metodoId)?.nombre} cubre el resto: {pesos(pagos[0].monto)}.
              </p>
            </div>
          )}
          {cobro.elegidos.length <= 1 && (
            <p className="mt-3 text-sm text-cafe-suave">Pago mixto: puedes repartir el total entre varios métodos.</p>
          )}
          {metodoEfectivo && (
            <div className="mt-3">
              <CampoDinero
                etiqueta="Recibe en efectivo (para el cambio)"
                valor={cobro.recibido}
                alCambiar={(v) => alCambiarCobro({ ...cobro, recibido: v })}
              />
              {cambio !== null && cambio >= 0 && (
                <p className="mt-2 text-[16px] font-semibold text-exito-texto">Cambio: {pesos(cambio)}</p>
              )}
            </div>
          )}
        </fieldset>
      )}

      <div className="mt-auto pt-6">
        {bloqueo && carrito.lineas.length > 0 && <p className="mb-2 text-sm text-cafe-medio">{bloqueo}</p>}
        <button
          type="button"
          onClick={alCobrar}
          disabled={bloqueo !== null || cobrando}
          className="h-[62px] w-full rounded-[16px] bg-fucsia text-[20px] font-bold text-white transition-colors hover:bg-fucsia-oscuro disabled:cursor-not-allowed disabled:opacity-60"
        >
          {cobrando ? 'Cobrando…' : `Cobrar ${pesos(t.cobrar)}`}
        </button>
      </div>
    </div>
  )
}
