import { useSearchParams } from 'react-router'
import { useSesion } from '../../auth/contexto'
import { Pildoras } from '../../components/formulario'
import { EncabezadoPagina } from '../../components/ui'
import { CajaHoy } from './CajaHoy'
import { Cierre } from './Cierre'
import { Historial } from './Historial'
import { useCaja } from './usarCaja'

type Seccion = 'hoy' | 'cierre' | 'historial'

/** Caja del día, cierre con arqueo (mockup "Cierre de caja") e historial de cierres. */
export function Caja() {
  const { puede } = useSesion()
  const caja = useCaja()
  const [params, setParams] = useSearchParams()
  const abierta = caja.data?.abierta ?? false
  const secciones: { valor: Seccion; texto: string; visible: boolean }[] = [
    { valor: 'hoy', texto: 'Caja de hoy', visible: true },
    { valor: 'cierre', texto: 'Cerrar caja', visible: puede('caja.cerrar') && (abierta || params.get('seccion') === 'cierre') },
    {
      valor: 'historial',
      texto: 'Historial de cierres',
      visible: ['caja.cerrar', 'reportes.ver', 'reportes.ver_caja_propia'].some(puede),
    },
  ]
  const visibles = secciones.filter((s) => s.visible)
  const actual = visibles.find((s) => s.valor === params.get('seccion'))?.valor ?? 'hoy'

  const navegacion = visibles.length > 1 && (
    <div className="mb-5">
      <Pildoras etiqueta="Secciones de caja" opciones={visibles} valor={actual} alCambiar={(v) => setParams({ seccion: v })} />
    </div>
  )

  // El cierre lleva su propio encabezado, como el mockup: "Caja del viernes… · abierta… · base…".
  if (actual === 'cierre') {
    return <Cierre navegacion={navegacion} alCerrada={(id) => setParams({ seccion: 'historial', sesion: id })} />
  }
  return (
    <>
      <EncabezadoPagina contexto="El dinero del turno: lo que entra, lo que sale y el arqueo" titulo="Caja" />
      {navegacion}
      {actual === 'hoy' && <CajaHoy alCerrar={() => setParams({ seccion: 'cierre' })} />}
      {actual === 'historial' && (
        <Historial elegida={params.get('sesion') ?? undefined} alElegir={(id) => setParams({ seccion: 'historial', sesion: id })} />
      )}
    </>
  )
}
