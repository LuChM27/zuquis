import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Aviso, Celda, FilaTabla, ListaDetalle, Tabla, Vacio } from '../../components/formulario'
import { api } from '../../lib/api'
import { pesos } from '../../lib/formato'
import type { Compra, CuentaPorPagar, Pagina } from '../../lib/tipos'
import { TarjetaLista } from '../configuracion/comun'
import { fechaIso } from '../../lib/unidades'
import { DetalleCompra } from './ListaCompras'

/** Cuentas por pagar por proveedor; al elegir una, sus compras pendientes y el pago. */
export function PorPagar() {
  const cuentas = useQuery({ queryKey: ['compras', 'por-pagar'], queryFn: () => api<CuentaPorPagar[]>('/compras/por-pagar') })
  const pendientes = useQuery({
    queryKey: ['compras', 'lista', 'pendientes'],
    queryFn: () => api<Pagina<Compra>>('/compras?estado_pago=por_pagar&size=200'),
  })
  const [proveedor, setProveedor] = useState<string | null | undefined>(undefined)
  const [compraId, setCompraId] = useState<string>()
  const lista = cuentas.data ?? []
  const elegido = proveedor === undefined ? lista[0]?.proveedor_id : proveedor
  const compras = (pendientes.data?.items ?? []).filter((c) => !c.anulada && c.proveedor_id === (elegido ?? null))
  const actual = compras.find((c) => c.id === compraId)?.id ?? compras[0]?.id
  const total = lista.reduce((s, c) => s + c.saldo, 0)

  return (
    <ListaDetalle
      lista={
        <div className="flex min-w-0 flex-col gap-4">
          <TarjetaLista titulo="Cuentas por pagar">
            {cuentas.isError && <Aviso>No pudimos cargar las cuentas por pagar.</Aviso>}
            {cuentas.isSuccess && lista.length === 0 && <Vacio>No hay compras pendientes de pago.</Vacio>}
            {lista.length > 0 && (
              <>
                <p className="mb-3 text-cafe-medio">
                  Se deben <strong className="text-cafe">{pesos(total)}</strong> a {lista.length}{' '}
                  {lista.length === 1 ? 'proveedor' : 'proveedores'}.
                </p>
                <Tabla
                  columnas={[
                    { texto: 'Proveedor' },
                    { texto: 'Compras', derecha: true, ocultarMovil: true },
                    { texto: 'Desde', ocultarMovil: true },
                    { texto: 'Saldo', derecha: true },
                  ]}
                >
                  {lista.map((c) => (
                    <FilaTabla
                      key={c.proveedor_id ?? 'sin'}
                      seleccionada={c.proveedor_id === elegido}
                      alElegir={() => {
                        setProveedor(c.proveedor_id)
                        setCompraId(undefined)
                      }}
                    >
                      <Celda className="font-semibold">{c.proveedor}</Celda>
                      <Celda derecha ocultarMovil>{c.compras}</Celda>
                      <Celda ocultarMovil className="whitespace-nowrap text-cafe-medio">{fechaIso(c.mas_antigua)}</Celda>
                      <Celda derecha className="font-semibold whitespace-nowrap text-peligro-texto">{pesos(c.saldo)}</Celda>
                    </FilaTabla>
                  ))}
                </Tabla>
              </>
            )}
          </TarjetaLista>
          {compras.length > 0 && (
            <TarjetaLista titulo="Compras pendientes">
              <Tabla columnas={[{ texto: 'Fecha' }, { texto: 'Factura', ocultarMovil: true }, { texto: 'Total', derecha: true }, { texto: 'Saldo', derecha: true }]}>
                {compras.map((c) => (
                  <FilaTabla key={c.id} seleccionada={c.id === actual} alElegir={() => setCompraId(c.id)}>
                    <Celda className="whitespace-nowrap">{fechaIso(c.fecha)}</Celda>
                    <Celda ocultarMovil className="text-cafe-medio">{c.numero_factura_proveedor ?? '—'}</Celda>
                    <Celda derecha className="whitespace-nowrap">{pesos(c.total)}</Celda>
                    <Celda derecha className="font-semibold whitespace-nowrap">{pesos(c.saldo)}</Celda>
                  </FilaTabla>
                ))}
              </Tabla>
            </TarjetaLista>
          )}
        </div>
      }
      detalle={actual ? <DetalleCompra key={actual} id={actual} /> : null}
    />
  )
}
