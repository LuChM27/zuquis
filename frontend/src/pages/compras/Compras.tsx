import { useSearchParams } from 'react-router'
import { useSesion } from '../../auth/contexto'
import { Pildoras } from '../../components/formulario'
import { EncabezadoPagina } from '../../components/ui'
import { ListaCompras } from './ListaCompras'
import { NuevaCompra } from './NuevaCompra'
import { PorPagar } from './PorPagar'
import { Produccion } from './Produccion'
import { Proveedores } from './Proveedores'

type Seccion = 'nueva' | 'compras' | 'por-pagar' | 'proveedores' | 'produccion'

const SECCIONES: { valor: Seccion; texto: string; permisos: string[] }[] = [
  { valor: 'nueva', texto: 'Registrar compra', permisos: ['compras.crear'] },
  { valor: 'compras', texto: 'Compras', permisos: ['compras.crear'] },
  { valor: 'por-pagar', texto: 'Cuentas por pagar', permisos: ['compras.crear'] },
  { valor: 'proveedores', texto: 'Proveedores', permisos: ['proveedores.gestionar', 'compras.crear'] },
  { valor: 'produccion', texto: 'Producción', permisos: ['produccion.crear'] },
]

/** Compras, proveedores, cuentas por pagar y producción (decisión del 13/11/2026). */
export function Compras() {
  const { puede } = useSesion()
  const [params, setParams] = useSearchParams()
  const visibles = SECCIONES.filter((s) => s.permisos.some(puede))
  const actual = visibles.find((s) => s.valor === params.get('seccion')) ?? visibles[0]
  const compra = params.get('compra') ?? undefined

  return (
    <>
      <EncabezadoPagina contexto="Insumos que entran, lo que se debe y lo que se produce" titulo="Compras" />
      <div className="mb-4">
        <Pildoras
          etiqueta="Secciones de compras"
          opciones={visibles}
          valor={actual?.valor ?? 'nueva'}
          alCambiar={(v) => setParams({ seccion: v })}
        />
      </div>
      {actual?.valor === 'nueva' && <NuevaCompra alRegistrar={(c) => setParams({ seccion: 'compras', compra: c.id })} />}
      {actual?.valor === 'compras' && (
        <ListaCompras elegida={compra} alElegir={(id) => setParams({ seccion: 'compras', compra: id })} />
      )}
      {actual?.valor === 'por-pagar' && <PorPagar />}
      {actual?.valor === 'proveedores' && <Proveedores />}
      {actual?.valor === 'produccion' && <Produccion />}
    </>
  )
}
