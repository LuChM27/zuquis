import { Pildoras } from '../../components/formulario'
import { Campo } from '../../components/ui'
import { atajo, type Atajo, type Rango } from '../../lib/reportes'

const ATAJOS: { valor: Atajo | 'rango'; texto: string }[] = [
  { valor: 'hoy', texto: 'Hoy' },
  { valor: 'ayer', texto: 'Ayer' },
  { valor: 'semana', texto: 'Semana' },
  { valor: 'mes', texto: 'Mes' },
  { valor: 'rango', texto: 'Rango' },
]

/** Cuál atajo corresponde al rango actual (o "rango" si es uno a mano). */
function atajoDe(r: Rango, hoy = new Date()): Atajo | 'rango' {
  for (const a of ['hoy', 'ayer', 'semana', 'mes'] as Atajo[]) {
    const x = atajo(a, hoy)
    if (x.desde === r.desde && x.hasta === r.hasta) return a
  }
  return 'rango'
}

export function FiltroRango({ rango, alCambiar, manual, alManual }: { rango: Rango; alCambiar: (r: Rango) => void; manual: boolean; alManual: (v: boolean) => void }) {
  const actual = manual ? 'rango' : atajoDe(rango)
  return (
    <div className="flex flex-col gap-3">
      <Pildoras
        etiqueta="Rango de fechas"
        opciones={ATAJOS}
        valor={actual}
        alCambiar={(v) => {
          alManual(v === 'rango')
          if (v !== 'rango') alCambiar({ ...atajo(v), sedeId: rango.sedeId })
        }}
      />
      {actual === 'rango' && (
        <div className="flex flex-wrap gap-3">
          <Campo etiqueta="Desde" type="date" value={rango.desde} max={rango.hasta} onChange={(e) => e.target.value && alCambiar({ ...rango, desde: e.target.value })} />
          <Campo etiqueta="Hasta" type="date" value={rango.hasta} min={rango.desde} onChange={(e) => e.target.value && alCambiar({ ...rango, hasta: e.target.value })} />
        </div>
      )}
    </div>
  )
}
