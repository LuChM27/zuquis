import { TriangleAlert } from 'lucide-react'
import { lazy, Suspense, useMemo } from 'react'
import { Link } from 'react-router'
import { useYo } from '../../auth/contexto'
import { BASE, COLORES, enMiles, etiquetaHora, resaltarMaximo } from '../../components/graficos/tema'
import { Chip, EncabezadoPagina, Tarjeta, TituloTarjeta } from '../../components/ui'
import { unir } from '../../lib/clases'
import { fechaConDia, hora, pesos, saludo } from '../../lib/formato'
import { useDashboard, type Alerta, type Dashboard as Datos } from '../../lib/reportes'

// ECharts se carga aparte: Vender y el resto de la app no lo descargan.
const Grafico = lazy(() => import('../../components/graficos/Grafico'))

const ENLACE = 'text-[15px] font-semibold text-fucsia underline underline-offset-4 hover:text-fucsia-oscuro'

function Cifra({ titulo, valor, detalle }: { titulo: string; valor: string; detalle: string }) {
  return (
    <Tarjeta className="p-6">
      <p className="text-[15px] font-medium text-cafe-medio">{titulo}</p>
      <p className="mt-2 font-serif text-[40px] leading-none font-semibold lg:text-[44px]">{valor}</p>
      <p className="mt-3 text-sm text-cafe-medio">{detalle}</p>
    </Tarjeta>
  )
}

function VentasPorHora({ d }: { d: Datos }) {
  const opcion = useMemo(() => {
    const valores = d.por_hora.map((f) => f.ventas)
    const colores = resaltarMaximo(valores)
    return {
      ...BASE,
      tooltip: { ...BASE.tooltip, valueFormatter: (v: number) => pesos(v) },
      xAxis: {
        type: 'category',
        data: d.por_hora.map((f) => etiquetaHora(Number(f.clave))),
        axisTick: { show: false },
        axisLine: { lineStyle: { color: COLORES.linea } },
      },
      yAxis: { type: 'value', show: false },
      series: [
        {
          type: 'bar',
          barMaxWidth: 56,
          data: valores.map((v, i) => ({ value: v, itemStyle: { color: colores[i], borderRadius: [8, 8, 0, 0] } })),
          label: { show: true, position: 'top', formatter: ({ value }: { value: number }) => enMiles(value), color: COLORES.cafe, fontWeight: 600 },
        },
      ],
    }
  }, [d.por_hora])
  if (!d.por_hora.length) return <p className="py-16 text-center text-cafe-suave">Todavía no hay ventas hoy.</p>
  return (
    <Suspense fallback={<div className="h-[260px]" />}>
      <Grafico opcion={opcion} alto={260} etiqueta="Ventas por hora" />
    </Suspense>
  )
}

function ComoPagaron({ d }: { d: Datos }) {
  if (!d.por_metodo.length) return <p className="py-6 text-cafe-suave">Sin pagos todavía.</p>
  return (
    <ul className="flex flex-col gap-5">
      {d.por_metodo.map((f) => {
        const pct = d.porcentaje_metodo[f.etiqueta] ?? '0'
        return (
          <li key={f.clave}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="font-semibold">{f.etiqueta}</span>
              <span className="text-cafe-medio tabular-nums">{`${pesos(f.ventas)} · ${Math.round(Number(pct))}%`}</span>
            </div>
            <div className="mt-2 h-3 rounded-full bg-pista">
              <div className="h-3 rounded-full bg-fucsia" style={{ width: `${Math.min(Number(pct), 100)}%` }} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

function MasVendidos({ d }: { d: Datos }) {
  if (!d.mas_vendidos.length) return <p className="py-6 text-cafe-suave">Sin ventas todavía.</p>
  return (
    <ol className="flex flex-col">
      {d.mas_vendidos.map((f, i) => (
        <li key={f.clave} className="flex items-center gap-4 border-b border-linea py-3.5 last:border-0">
          <span className="grid size-9 shrink-0 place-items-center rounded-full bg-rosa-suave font-semibold text-fucsia-oscuro">{i + 1}</span>
          <span className="min-w-0 flex-1 truncate">{f.etiqueta}</span>
          <span className="font-semibold whitespace-nowrap tabular-nums">{`${Number(f.unidades)} und`}</span>
        </li>
      ))}
    </ol>
  )
}

function EncargosHoy({ d }: { d: Datos }) {
  if (!d.encargos_hoy.length) return <p className="py-6 text-cafe-suave">No hay encargos para hoy.</p>
  return (
    <ul className="flex flex-col gap-3">
      {d.encargos_hoy.map((e) => (
        <li key={e.id} className="rounded-2xl border border-linea bg-crema px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <span className="font-semibold">{e.descripcion}</span>
            <span className="font-semibold whitespace-nowrap text-fucsia-oscuro">{hora(new Date(e.hora))}</span>
          </div>
          <p className="mt-1 text-sm text-cafe-medio">
            {`${e.cliente} · Saldo por cobrar ${pesos(e.saldo)}${e.saldo === 0 ? ' · pagado' : ''}`}
          </p>
        </li>
      ))}
    </ul>
  )
}

function Alertas({ alertas }: { alertas: Alerta[] }) {
  if (!alertas.length) return <p className="py-6 text-cafe-suave">Todo el inventario está bien.</p>
  return (
    <ul className="flex flex-col gap-3">
      {alertas.map((a, i) => {
        const peligro = a.tipo === 'bajo_minimo' || a.tipo === 'vencido' || a.tipo === 'faltante'
        return (
          <li key={i} className={unir('flex gap-3 rounded-2xl px-4 py-3', peligro ? 'bg-peligro-fondo' : 'bg-aviso-fondo')}>
            <TriangleAlert aria-hidden className={unir('mt-0.5 size-5 shrink-0', peligro ? 'text-peligro-texto' : 'text-aviso-texto')} />
            <div>
              <p className="font-semibold">{a.titulo}</p>
              <p className="text-sm text-cafe-medio">{a.detalle}</p>
            </div>
          </li>
        )
      })}
    </ul>
  )
}

/** Inicio · Dashboard (docs/mockups/dashboard.png). */
export function Dashboard() {
  const yo = useYo()
  const consulta = useDashboard()
  const d = consulta.data
  const ahora = new Date()
  const encabezado = (
    <EncabezadoPagina
      contexto={`${fechaConDia(ahora)} · ${yo.sede.nombre}`}
      titulo={saludo(ahora)}
      acciones={
        <>
          {d?.datos_ejemplo && <Chip tono="ejemplo">Datos de ejemplo</Chip>}
          <Link
            to="/vender"
            className="inline-flex h-12 items-center justify-center rounded-control bg-fucsia px-[26px] text-[17px] font-bold text-white hover:bg-fucsia-oscuro"
          >
            Nueva venta
          </Link>
        </>
      }
    />
  )
  if (consulta.isError) {
    return (
      <>
        {encabezado}
        <Tarjeta>
          <p className="text-cafe-medio">No pudimos cargar las cifras del día. Revisa la conexión e intenta de nuevo.</p>
        </Tarjeta>
      </>
    )
  }
  if (!d) {
    return (
      <>
        {encabezado}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4" aria-busy>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-[150px] animate-pulse rounded-tarjeta bg-pista" />
          ))}
        </div>
      </>
    )
  }
  return (
    <>
      {encabezado}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Cifra titulo="Ventas del día" valor={pesos(d.ventas)} detalle={`${d.n_ventas} ventas · sin contar propinas ni domicilios`} />
        <Cifra titulo="Gastos del día" valor={pesos(d.gastos)} detalle={`${d.n_gastos} ${d.n_gastos === 1 ? 'gasto registrado' : 'gastos registrados'}`} />
        <Cifra titulo="Ganancia estimada" valor={pesos(d.ganancia)} detalle="Ventas menos costo real de insumos y gastos" />
        <Cifra titulo="Ticket promedio" valor={pesos(d.ticket_promedio)} detalle="Por venta" />
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Tarjeta className="p-6">
          <TituloTarjeta>Ventas por hora</TituloTarjeta>
          <VentasPorHora d={d} />
        </Tarjeta>
        <Tarjeta className="p-6">
          <TituloTarjeta className="mb-5">Cómo pagaron hoy</TituloTarjeta>
          <ComoPagaron d={d} />
        </Tarjeta>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Tarjeta className="p-6">
          <TituloTarjeta className="mb-3">Más vendidos hoy</TituloTarjeta>
          <MasVendidos d={d} />
        </Tarjeta>
        <Tarjeta className="p-6">
          <div className="mb-4 flex items-baseline justify-between gap-3">
            <TituloTarjeta>Encargos para hoy</TituloTarjeta>
            <Link to="/encargos" className={ENLACE}>
              Ver todos
            </Link>
          </div>
          <EncargosHoy d={d} />
        </Tarjeta>
        <Tarjeta className="p-6">
          <div className="mb-4 flex items-baseline justify-between gap-3">
            <TituloTarjeta>Alertas de inventario</TituloTarjeta>
            <Link to="/inventario" className={ENLACE}>
              Ir a inventario
            </Link>
          </div>
          <Alertas alertas={d.alertas} />
        </Tarjeta>
      </div>
    </>
  )
}
