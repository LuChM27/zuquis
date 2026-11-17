import { memo, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'
import { useSesion, useYo } from '../../auth/contexto'
import { Pildoras, Selector } from '../../components/formulario'
import { EncabezadoPagina } from '../../components/ui'
import { atajo, TIPOS_VISIBLES, type Rango, type TipoReporte } from '../../lib/reportes'
import { FiltroRango } from './FiltroRango'
import { Graficos } from './Graficos'
import { Tablas } from './Tablas'

type Vista = 'graficos' | 'tablas'

const FECHA = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/
const GraficosMemo = memo(Graficos)

const mesLargo = new Intl.DateTimeFormat('es-CO', { day: 'numeric', month: 'long', timeZone: 'UTC' })
const diaSolo = new Intl.DateTimeFormat('es-CO', { day: 'numeric', timeZone: 'UTC' })

/** "Del 9 al 15 de noviembre", "Del 28 de octubre al 3 de noviembre", "12 de noviembre". */
function textoRango(r: Rango): string {
  const a = new Date(`${r.desde}T12:00:00Z`)
  const b = new Date(`${r.hasta}T12:00:00Z`)
  if (r.desde === r.hasta) return mesLargo.format(b)
  const mismoMes = r.desde.slice(0, 7) === r.hasta.slice(0, 7)
  return `Del ${mismoMes ? diaSolo.format(a) : mesLargo.format(a)} al ${mesLargo.format(b)}`
}

/** Reportes: pestaña de gráficos (galería de 14) y de tablas exportables (RF-42, RF-43). */
export function Reportes() {
  const yo = useYo()
  const { puede } = useSesion()
  const [params, setParams] = useSearchParams()
  const [manual, setManual] = useState(false)

  const verGraficos = puede('reportes.ver') || puede('reportes.ver_inventario')
  const tipos = TIPOS_VISIBLES(yo.permisos)
  const desdeUrl = params.get('desde')
  const hastaUrl = params.get('hasta')
  const sedeUrl = params.get('sede') ?? undefined
  // Memorizado: los gráficos solo se recalculan si cambia el rango, no en cada render.
  const rango: Rango = useMemo(() => {
    const valido = (f: string | null): f is string => !!f && FECHA.test(f) && !Number.isNaN(Date.parse(f))
    if (valido(desdeUrl) && valido(hastaUrl) && desdeUrl <= hastaUrl) return { desde: desdeUrl, hasta: hastaUrl, sedeId: sedeUrl }
    return { ...atajo('semana'), sedeId: sedeUrl }
  }, [desdeUrl, hastaUrl, sedeUrl])
  const vista: Vista = verGraficos && params.get('vista') !== 'tablas' ? 'graficos' : 'tablas'
  const pedido = params.get('reporte') as TipoReporte | null
  const tipo = pedido && tipos.includes(pedido) ? pedido : tipos[0]
  const sede = yo.sedes.find((s) => s.id === rango.sedeId) ?? yo.sede

  function cambiar(cambios: Record<string, string | undefined>) {
    const nuevo = new URLSearchParams(params)
    for (const [k, v] of Object.entries(cambios)) {
      if (v) nuevo.set(k, v)
      else nuevo.delete(k)
    }
    setParams(nuevo, { replace: true })
  }

  return (
    <>
      <EncabezadoPagina contexto={`${textoRango(rango)} · ${sede.nombre}`} titulo="Reportes" />
      <div className="mb-6 flex flex-col gap-4">
        {verGraficos && (
          <Pildoras
            etiqueta="Vista"
            opciones={[
              { valor: 'graficos' as Vista, texto: 'Gráficos' },
              { valor: 'tablas' as Vista, texto: 'Tablas' },
            ]}
            valor={vista}
            alCambiar={(v) => cambiar({ vista: v })}
          />
        )}
        <div className="flex flex-wrap items-end gap-4">
          <FiltroRango rango={rango} manual={manual} alManual={setManual} alCambiar={(r) => cambiar({ desde: r.desde, hasta: r.hasta })} />
          {yo.sedes.length > 1 && puede('reportes.ver') && (
            <Selector etiqueta="Sede" value={sede.id} onChange={(e) => cambiar({ sede: e.target.value === yo.sede.id ? undefined : e.target.value })}>
              {yo.sedes.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nombre}
                </option>
              ))}
            </Selector>
          )}
        </div>
      </div>
      {vista === 'graficos' ? (
        <GraficosMemo rango={rango} completo={puede('reportes.ver')} />
      ) : tipo ? (
        <Tablas rango={rango} tipos={tipos} tipo={tipo} alCambiarTipo={(t) => cambiar({ reporte: t })} puedeExportar={puede('reportes.exportar')} />
      ) : null}
    </>
  )
}
