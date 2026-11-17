import { FileSpreadsheet, FileText } from 'lucide-react'
import { useState } from 'react'
import { Aviso, Selector } from '../../components/formulario'
import { Boton } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { ErrorApi } from '../../lib/api'
import { exportar, NOMBRES_REPORTE, useReporte, type Rango, type TipoReporte } from '../../lib/reportes'
import { mensajeDeError } from '../configuracion/acciones'
import { TablaReporte } from './TablaReporte'

/** Pestaña "Tablas": un reporte a la vez, con exportación a Excel y PDF. */
export function Tablas({
  rango,
  tipos,
  tipo,
  alCambiarTipo,
  puedeExportar,
}: {
  rango: Rango
  tipos: TipoReporte[]
  tipo: TipoReporte
  alCambiarTipo: (t: TipoReporte) => void
  puedeExportar: boolean
}) {
  const reporte = useReporte(tipo, rango)
  const avisos = useAvisos()
  const [bajando, setBajando] = useState<'xlsx' | 'pdf' | null>(null)

  async function bajar(formato: 'xlsx' | 'pdf') {
    setBajando(formato)
    try {
      await exportar(tipo, rango, formato)
    } catch (e) {
      avisos.avisar(e instanceof ErrorApi ? mensajeDeError(e) : 'No pudimos generar el archivo. Intenta de nuevo.', 'error')
    } finally {
      setBajando(null)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Selector etiqueta="Reporte" value={tipo} onChange={(e) => alCambiarTipo(e.target.value as TipoReporte)} className="min-w-[260px]">
          {tipos.map((t) => (
            <option key={t} value={t}>
              {NOMBRES_REPORTE[t]}
            </option>
          ))}
        </Selector>
        {puedeExportar && (
          <div className="flex flex-wrap gap-3">
            <Boton variante="secundario" disabled={bajando !== null} onClick={() => bajar('xlsx')}>
              <FileSpreadsheet aria-hidden className="size-5" />
              {bajando === 'xlsx' ? 'Generando…' : 'Exportar a Excel'}
            </Boton>
            <Boton variante="secundario" disabled={bajando !== null} onClick={() => bajar('pdf')}>
              <FileText aria-hidden className="size-5" />
              {bajando === 'pdf' ? 'Generando…' : 'Exportar a PDF'}
            </Boton>
          </div>
        )}
      </div>
      {reporte.isError && <Aviso>{reporte.error instanceof ErrorApi ? mensajeDeError(reporte.error) : 'No pudimos cargar el reporte. Revisa la conexión.'}</Aviso>}
      {reporte.isPending && <div className="h-[240px] animate-pulse rounded-tarjeta bg-pista" />}
      {reporte.data?.secciones.map((s) => <TablaReporte key={s.titulo} seccion={s} />)}
    </div>
  )
}
