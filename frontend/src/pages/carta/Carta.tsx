import { useSearchParams } from 'react-router'
import { useSesion } from '../../auth/contexto'
import { Pildoras } from '../../components/formulario'
import { EncabezadoPagina } from '../../components/ui'
import { Adiciones } from './Adiciones'
import { Categorias } from './Categorias'
import { Insumos } from './Insumos'
import { Productos } from './Productos'

type Seccion = 'productos' | 'categorias' | 'adiciones' | 'insumos'

/** Quien edita recetas (Producción) ve productos y adiciones para llegar a ellas. */
const SECCIONES: { valor: Seccion; texto: string; permisos: string[] }[] = [
  { valor: 'productos', texto: 'Productos y recetas', permisos: ['carta.editar', 'recetas.editar'] },
  { valor: 'categorias', texto: 'Categorías', permisos: ['carta.editar'] },
  { valor: 'adiciones', texto: 'Adiciones', permisos: ['carta.editar', 'recetas.editar'] },
  { valor: 'insumos', texto: 'Insumos', permisos: ['insumos.gestionar'] },
]

export function Carta() {
  const { puede } = useSesion()
  const [params, setParams] = useSearchParams()
  const visibles = SECCIONES.filter((s) => s.permisos.some(puede))
  const actual = visibles.find((s) => s.valor === params.get('seccion')) ?? visibles[0]

  return (
    <>
      <EncabezadoPagina contexto="Productos, precios, recetas y costo teórico" titulo="Carta" />
      <div className="mb-4">
        <Pildoras
          etiqueta="Secciones de la carta"
          opciones={visibles}
          valor={actual?.valor ?? 'productos'}
          alCambiar={(v) => setParams({ seccion: v })}
        />
      </div>
      {actual?.valor === 'productos' && <Productos />}
      {actual?.valor === 'categorias' && <Categorias />}
      {actual?.valor === 'adiciones' && <Adiciones />}
      {actual?.valor === 'insumos' && <Insumos />}
    </>
  )
}
