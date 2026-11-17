import { BarChart, HeatmapChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { init, use as registrar, type EChartsCoreOption } from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { useEffect, useRef } from 'react'

// Solo los módulos que se usan: el chunk de gráficos queda pequeño y se carga en diferido.
registrar([BarChart, LineChart, HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent, LegendComponent, SVGRenderer])

/** Gráfico ECharts con su tamaño atado al contenedor. Se importa con React.lazy. */
export default function Grafico({ opcion, alto = 220, etiqueta }: { opcion: EChartsCoreOption; alto?: number; etiqueta: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const grafico = useRef<ReturnType<typeof init> | null>(null)

  useEffect(() => {
    if (!ref.current) return
    const g = init(ref.current, undefined, { renderer: 'svg' })
    grafico.current = g
    const observador = new ResizeObserver(() => g.resize())
    observador.observe(ref.current)
    return () => {
      observador.disconnect()
      g.dispose()
      grafico.current = null
    }
  }, [])

  useEffect(() => {
    grafico.current?.setOption(opcion, true)
  }, [opcion])

  return <div ref={ref} role="img" aria-label={etiqueta} style={{ height: alto, width: '100%' }} />
}
