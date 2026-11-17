import type { EChartsCoreOption } from 'echarts/core'
import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from 'react'
import { BASE, COLORES, enMiles, etiquetaHora } from '../../components/graficos/tema'
import { Tarjeta } from '../../components/ui'
import { unir } from '../../lib/clases'
import { pesos } from '../../lib/formato'
import { useGrupoGraficos, type DatosGrupo, type Grupo, type Rango } from '../../lib/reportes'
import { fechaIso } from '../../lib/unidades'

const Grafico = lazy(() => import('../../components/graficos/Grafico'))

const DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
const ejePesos = { type: 'value', axisLabel: { formatter: (v: number) => enMiles(v) }, splitLine: { lineStyle: { color: COLORES.linea } } }
const tooltipPesos = { ...BASE.tooltip, valueFormatter: (v: number) => pesos(Math.round(v)) }
const diaCorto = (iso: string) => fechaIso(iso).slice(0, 5)

/** Pide los datos de un grupo solo cuando su sección aparece en pantalla. */
function useVisible<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [visible, setVisible] = useState(typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    if (visible || !ref.current) return
    const obs = new IntersectionObserver(([e]) => e.isIntersecting && setVisible(true), { rootMargin: '200px' })
    obs.observe(ref.current)
    return () => obs.disconnect()
  }, [visible])
  return { ref, visible }
}

function Vacio() {
  return <p className="py-10 text-center text-cafe-suave">Sin datos en este rango</p>
}

function Tarjeta_({ titulo, detalle, children, ancho }: { titulo: string; detalle: string; children: ReactNode; ancho?: boolean }) {
  return (
    <Tarjeta className={unir('min-w-0 p-5', ancho && 'md:col-span-2')}>
      <h3 className="font-serif text-[22px] leading-tight font-semibold">{titulo}</h3>
      <p className="mb-3 text-sm text-cafe-suave">{detalle}</p>
      {children}
    </Tarjeta>
  )
}

function G({ opcion, etiqueta, alto = 220 }: { opcion: EChartsCoreOption; etiqueta: string; alto?: number }) {
  return (
    <Suspense fallback={<div style={{ height: alto }} />}>
      <Grafico opcion={opcion} etiqueta={etiqueta} alto={alto} />
    </Suspense>
  )
}

function barras(etiquetas: string[], series: { nombre: string; datos: number[]; color: string; pila?: string }[], horizontal = false) {
  const categorias = { type: 'category', data: etiquetas, axisTick: { show: false }, axisLine: { lineStyle: { color: COLORES.linea } } }
  return {
    ...BASE,
    tooltip: tooltipPesos,
    legend: series.length > 1 ? { bottom: 0, textStyle: { color: COLORES.cafeSuave } } : undefined,
    grid: { ...BASE.grid, bottom: series.length > 1 ? 32 : 8 },
    xAxis: horizontal ? ejePesos : categorias,
    yAxis: horizontal ? { ...categorias, inverse: true } : ejePesos,
    series: series.map((s) => ({ name: s.nombre, type: 'bar', stack: s.pila, data: s.datos, itemStyle: { color: s.color, borderRadius: 4 }, barMaxWidth: 36 })),
  }
}

function Lista({ filas }: { filas: [string, string][] }) {
  return (
    <ul className="flex flex-col">
      {filas.map(([a, b], i) => (
        <li key={i} className="flex justify-between gap-3 border-b border-linea py-2 text-[15px] last:border-0">
          <span className="min-w-0 truncate">{a}</span>
          <span className="font-semibold whitespace-nowrap tabular-nums">{b}</span>
        </li>
      ))}
    </ul>
  )
}

// --- Grupos ---------------------------------------------------------------------------------

function Ganancia({ d }: { d: DatosGrupo['ganancia'] }) {
  const c = d.cascada
  const pasos: [string, number][] = [
    ['Ventas', c.ventas],
    ['Insumos', -c.costo_insumos],
    ['Regalado', -c.regalado],
    ['Gastos', -c.gastos],
    ['Mermas', -c.mermas],
    ['Cancelaciones', c.ingresos_cancelacion],
  ]
  let acumulado = 0
  const base: number[] = []
  const valor: { value: number; itemStyle: { color: string } }[] = []
  for (const [, v] of pasos) {
    const desde = v >= 0 ? acumulado : acumulado + v
    base.push(Math.max(Math.min(desde, acumulado + v), 0))
    valor.push({ value: Math.abs(v), itemStyle: { color: v >= 0 ? COLORES.rosaBarra : COLORES.peligro } })
    acumulado += v
  }
  base.push(0)
  valor.push({ value: c.utilidad, itemStyle: { color: c.utilidad >= 0 ? COLORES.fucsia : COLORES.peligro } })
  const cascada = {
    ...BASE,
    tooltip: { ...tooltipPesos, formatter: (p: { name: string; value: number }[]) => `${p[1].name}: ${pesos(p[1].value)}` },
    xAxis: { type: 'category', data: [...pasos.map(([n]) => n), 'Utilidad'], axisTick: { show: false } },
    yAxis: ejePesos,
    series: [
      { type: 'bar', stack: 'c', data: base, itemStyle: { color: 'transparent' }, emphasis: { disabled: true } },
      { type: 'bar', stack: 'c', data: valor, barMaxWidth: 44, label: { show: true, position: 'top', formatter: ({ value }: { value: number }) => enMiles(value) } },
    ],
  }
  const pct = {
    ...BASE,
    tooltip: { ...BASE.tooltip, valueFormatter: (v: number) => `${v} %` },
    xAxis: { type: 'category', data: d.costo_pct.map((s) => s.semana.replace(/^\d{4}-W/, 'Sem ')) },
    yAxis: { type: 'value', axisLabel: { formatter: '{value} %' }, splitLine: { lineStyle: { color: COLORES.linea } } },
    series: [{ type: 'bar', data: d.costo_pct.map((s) => Number(s.pct)), itemStyle: { color: COLORES.rosaBarra, borderRadius: 4 }, barMaxWidth: 36, label: { show: true, position: 'top', formatter: '{c} %' } }],
  }
  const flujo = barras(
    d.flujo.map((f) => diaCorto(f.dia)),
    [
      { nombre: 'Entra al negocio', datos: d.flujo.map((f) => f.entra_negocio), color: COLORES.rosaBarra, pila: 'entra' },
      { nombre: 'Entra a los dueños', datos: d.flujo.map((f) => f.entra_dueno), color: COLORES.fucsia, pila: 'entra' },
      { nombre: 'Sale', datos: d.flujo.map((f) => f.sale), color: COLORES.dorado },
    ],
  )
  return (
    <>
      <Tarjeta_ titulo="Cascada de utilidad" detalle="Ventas menos insumos, regalado, gastos y mermas">
        {c.ventas || c.gastos ? <G opcion={cascada} etiqueta={`Cascada de utilidad: utilidad ${pesos(c.utilidad)}`} /> : <Vacio />}
      </Tarjeta_>
      <Tarjeta_ titulo="Costo de insumos %" detalle="Semana a semana, sobre lo vendido">
        {d.costo_pct.length ? <G opcion={pct} etiqueta="Costo de insumos como porcentaje de las ventas" /> : <Vacio />}
      </Tarjeta_>
      <Tarjeta_ titulo="Flujo de caja" detalle="Lo que entra y lo que sale por día">
        {d.flujo.length ? <G opcion={flujo} etiqueta="Flujo de caja por día" /> : <Vacio />}
      </Tarjeta_>
    </>
  )
}

function Ventas({ d }: { d: DatosGrupo['ventas'] }) {
  const diaADia = {
    ...BASE,
    tooltip: tooltipPesos,
    legend: { bottom: 0, textStyle: { color: COLORES.cafeSuave } },
    grid: { ...BASE.grid, bottom: 32 },
    xAxis: { type: 'category', data: d.dia_a_dia.map((f) => diaCorto(f.dia)) },
    yAxis: ejePesos,
    series: [
      { name: 'Este periodo', type: 'bar', data: d.dia_a_dia.map((f) => f.ventas), itemStyle: { color: COLORES.rosaBarra, borderRadius: 4 }, barMaxWidth: 36 },
      { name: 'Periodo anterior', type: 'line', data: d.anterior.map((f) => f.ventas), lineStyle: { type: 'dashed', color: COLORES.dorado }, itemStyle: { color: COLORES.dorado } },
    ],
  }
  const max = Math.max(1, ...d.calor.map((c) => c.ventas))
  const horas = [...new Set(d.calor.map((c) => c.hora))].sort((a, b) => a - b)
  const calor = {
    ...BASE,
    tooltip: { ...BASE.tooltip, trigger: 'item', formatter: (p: { value: [number, number, number] }) => `${DIAS[p.value[1]]} ${etiquetaHora(horas[p.value[0]])}: ${pesos(p.value[2])}` },
    grid: { ...BASE.grid, bottom: 40 },
    xAxis: { type: 'category', data: horas.map(etiquetaHora), splitArea: { show: true } },
    yAxis: { type: 'category', data: DIAS, inverse: true },
    visualMap: { min: 0, max, show: false, inRange: { color: [COLORES.rosaSuave, COLORES.fucsia] } },
    series: [{ type: 'heatmap', data: d.calor.map((c) => [horas.indexOf(c.hora), c.dow - 1, c.ventas]) }],
  }
  const categorias = barras(
    d.categorias.map((c) => c.categoria),
    [{ nombre: 'Ventas', datos: d.categorias.map((c) => c.ventas), color: COLORES.fucsia }],
    true,
  )
  return (
    <>
      <Tarjeta_ titulo="Ventas día a día" detalle="Comparadas con el periodo anterior">
        {d.dia_a_dia.length ? <G opcion={diaADia} etiqueta="Ventas por día" /> : <Vacio />}
      </Tarjeta_>
      <Tarjeta_ titulo="Día de la semana y hora" detalle="Más oscuro: se vende más">
        {d.calor.length ? <G opcion={calor} etiqueta="Mapa de calor de ventas por día y hora" /> : <Vacio />}
      </Tarjeta_>
      <Tarjeta_ titulo="Ventas por categoría" detalle="Antes del descuento sobre el total de la venta">
        {d.categorias.length ? <G opcion={categorias} etiqueta="Ventas por categoría" alto={Math.max(160, d.categorias.length * 34)} /> : <Vacio />}
      </Tarjeta_>
    </>
  )
}

function Productos({ d }: { d: DatosGrupo['productos'] }) {
  const pv = d.producido_vendido
  const producido = barras(
    pv.map((p) => p.producto),
    [
      { nombre: 'Producido', datos: pv.map((p) => Number(p.producido)), color: COLORES.dorado },
      { nombre: 'Vendido', datos: pv.map((p) => Number(p.vendido)), color: COLORES.fucsia },
    ],
    true,
  )
  const unidades = { ...producido, tooltip: BASE.tooltip, xAxis: { type: 'value', splitLine: { lineStyle: { color: COLORES.linea } } } }
  return (
    <>
      {d.mas_vendidos && (
        <Tarjeta_ titulo="Los más vendidos y los que menos se mueven" detalle="En unidades">
          {d.mas_vendidos.length || d.menos_vendidos?.length ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="mb-1 text-sm font-semibold text-exito-texto">Más vendidos</p>
                <Lista filas={d.mas_vendidos.map((f) => [f.producto, `${Number(f.unidades)} und`])} />
              </div>
              <div>
                <p className="mb-1 text-sm font-semibold text-peligro-texto">Se mueven poco</p>
                <Lista filas={(d.menos_vendidos ?? []).map((f) => [f.producto, `${Number(f.unidades)} und`])} />
              </div>
            </div>
          ) : (
            <Vacio />
          )}
        </Tarjeta_>
      )}
      <Tarjeta_ titulo="Producido contra vendido" detalle="Productos de vitrina; la diferencia quedó en vitrina o se fue a merma">
        {pv.length ? <G opcion={unidades} etiqueta="Producido contra vendido" alto={Math.max(180, pv.length * 46)} /> : <Vacio />}
      </Tarjeta_>
    </>
  )
}

function Gastos({ d }: { d: DatosGrupo['gastos'] }) {
  const meses = [...new Set((d.por_categoria_mes ?? []).map((g) => g.mes))].sort()
  const categorias = [...new Set((d.por_categoria_mes ?? []).map((g) => g.categoria))]
  const paleta = [COLORES.fucsia, COLORES.rosaBarra, COLORES.dorado, COLORES.cafeSuave, COLORES.peligro]
  const gastos = barras(
    meses,
    categorias.map((c, i) => ({
      nombre: c,
      datos: meses.map((m) => d.por_categoria_mes?.find((g) => g.mes === m && g.categoria === c)?.monto ?? 0),
      color: paleta[i % paleta.length],
      pila: 'g',
    })),
  )
  const mermas = barras(
    d.mermas.por_motivo.map((m) => m.motivo),
    [{ nombre: 'Costo', datos: d.mermas.por_motivo.map((m) => m.costo), color: COLORES.peligro }],
    true,
  )
  const pp = d.por_pagar
  return (
    <>
      {pp && (
        <Tarjeta_ titulo="Gastos por categoría" detalle="Mes a mes">
          {meses.length ? <G opcion={gastos} etiqueta="Gastos por categoría y mes" /> : <Vacio />}
        </Tarjeta_>
      )}
      <Tarjeta_ titulo="Mermas" detalle="Por motivo, en pesos">
        {d.mermas.por_motivo.length ? (
          <>
            <G opcion={mermas} etiqueta="Mermas por motivo" alto={Math.max(120, d.mermas.por_motivo.length * 40)} />
            <Lista filas={d.mermas.por_item.slice(0, 5).map((m) => [m.item, pesos(m.costo)])} />
          </>
        ) : (
          <Vacio />
        )}
      </Tarjeta_>
      {pp && (
        <Tarjeta_ titulo="Cuentas por pagar" detalle="Por fecha límite; sin fecha, por antigüedad">
          <Lista
            filas={[
              ['Vencidas', pesos(pp.con_fecha.vencidas)],
              ['Vencen esta semana', pesos(pp.con_fecha.esta_semana)],
              ['Vencen después', pesos(pp.con_fecha.proximas)],
              ['Sin fecha · 0 a 15 días', pesos(pp.sin_fecha.d0_15)],
              ['Sin fecha · 16 a 30 días', pesos(pp.sin_fecha.d16_30)],
              ['Sin fecha · más de 30 días', pesos(pp.sin_fecha.d30_mas)],
            ]}
          />
        </Tarjeta_>
      )}
    </>
  )
}

function Encargos({ d }: { d: DatosGrupo['encargos'] }) {
  const semanas = d.por_semana.map((s) => s.semana.replace(/^\d{4}-W/, 'Sem '))
  const opcion = {
    ...barras(semanas, [
      { nombre: 'Entregados', datos: d.por_semana.map((s) => s.entregados), color: COLORES.rosaBarra },
      { nombre: 'Cancelados', datos: d.por_semana.map((s) => s.cancelados), color: COLORES.peligro },
    ]),
    tooltip: BASE.tooltip,
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: COLORES.linea } } },
  }
  return (
    <>
      <Tarjeta_ titulo="Encargos" detalle={`Abonos de encargos aún sin entregar: ${pesos(d.abonos_sin_entregar)}`}>
        {d.por_semana.length ? <G opcion={opcion} etiqueta="Encargos entregados y cancelados por semana" /> : <Vacio />}
      </Tarjeta_>
      <Tarjeta_ titulo="Clientes que más encargan" detalle="Encargos entregados en el rango">
        {d.clientes_top.length ? <Lista filas={d.clientes_top.map((c) => [c.cliente, `${c.encargos} · ${pesos(c.total)}`])} /> : <Vacio />}
      </Tarjeta_>
    </>
  )
}

function Cajeros({ d }: { d: DatosGrupo['cajeros'] }) {
  if (!d.por_cajero.length)
    return (
      <Tarjeta_ titulo="Por cajero" detalle="Ventas, descuentos y cierres">
        <Vacio />
      </Tarjeta_>
    )
  return (
    <Tarjeta_ titulo="Por cajero" detalle="Ventas, descuentos y regalos, y la diferencia en los cierres que contó" ancho>
      <div className="-mx-5 overflow-x-auto px-5">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-dorado-claro text-[13px] tracking-[0.08em] text-cafe-suave uppercase">
              <th className="py-2 pr-3">Cajero</th>
              <th className="px-3 py-2 text-right">Vendió</th>
              <th className="px-3 py-2 text-right">Descuentos</th>
              <th className="px-3 py-2 text-right">Regalos</th>
              <th className="py-2 pl-3 text-right">Diferencia</th>
            </tr>
          </thead>
          <tbody>
            {d.por_cajero.map((c) => (
              <tr key={c.cajero} className="border-b border-linea tabular-nums">
                <td className="py-2 pr-3">{c.cajero}</td>
                <td className="px-3 py-2 text-right">{pesos(c.vendido)}</td>
                <td className="px-3 py-2 text-right">{pesos(c.descuentos)}</td>
                <td className="px-3 py-2 text-right">{c.cortesias}</td>
                <td className={unir('py-2 pl-3 text-right', c.diferencia_cierres < 0 ? 'text-peligro-texto' : 'text-exito-texto')}>{pesos(c.diferencia_cierres)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Tarjeta_>
  )
}

const TITULOS: Record<Grupo, string> = {
  ganancia: '¿Estamos ganando?',
  ventas: '¿Cuándo y qué se vende?',
  productos: 'Productos',
  gastos: 'Gastos, mermas y proveedores',
  encargos: 'Encargos y clientes',
  cajeros: 'Por cajero',
}

function SeccionGrupo<G extends Grupo>({ grupo, rango }: { grupo: G; rango: Rango }) {
  const { ref, visible } = useVisible<HTMLElement>()
  const datos = useGrupoGraficos(grupo, rango, visible)
  let contenido: ReactNode = <div className="h-[220px] animate-pulse rounded-tarjeta bg-pista md:col-span-2 xl:col-span-3" />
  if (datos.isError) contenido = <p className="text-cafe-medio">No pudimos cargar estos gráficos.</p>
  else if (datos.data) {
    const d = datos.data as DatosGrupo[Grupo]
    contenido =
      grupo === 'ganancia' ? <Ganancia d={d as DatosGrupo['ganancia']} />
      : grupo === 'ventas' ? <Ventas d={d as DatosGrupo['ventas']} />
      : grupo === 'productos' ? <Productos d={d as DatosGrupo['productos']} />
      : grupo === 'gastos' ? <Gastos d={d as DatosGrupo['gastos']} />
      : grupo === 'encargos' ? <Encargos d={d as DatosGrupo['encargos']} />
      : <Cajeros d={d as DatosGrupo['cajeros']} />
  }
  return (
    <section ref={ref} aria-labelledby={`grupo-${grupo}`}>
      <h2 id={`grupo-${grupo}`} className="mt-7 mb-3 text-[13px] font-semibold tracking-[0.1em] text-cafe-suave uppercase">
        {TITULOS[grupo]}
      </h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">{contenido}</div>
    </section>
  )
}

/** Pestaña "Gráficos": los 14 gráficos en seis grupos; producción solo ve los de inventario. */
export function Graficos({ rango, completo }: { rango: Rango; completo: boolean }) {
  const grupos: Grupo[] = completo ? ['ganancia', 'ventas', 'productos', 'gastos', 'encargos', 'cajeros'] : ['productos', 'gastos']
  return (
    <div>
      {grupos.map((g) => (
        <SeccionGrupo key={g} grupo={g} rango={rango} />
      ))}
    </div>
  )
}
