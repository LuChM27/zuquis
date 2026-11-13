import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useSesion } from '../../auth/contexto'
import { Dialogo } from '../../components/Dialogo'
import { Aviso, ListaDetalle, PanelDetalle, Pildoras } from '../../components/formulario'
import { Boton, EncabezadoPagina, Tarjeta } from '../../components/ui'
import { api } from '../../lib/api'
import type { ResumenInventario, StockItem } from '../../lib/tipos'
import { hoyIso } from '../../lib/unidades'
import { resumenItem, useEsCelular } from './comun'
import { Detalle } from './Detalle'
import { FormAjuste, FormMerma } from './Formularios'
import { Indicadores } from './Indicadores'
import { ListaStock } from './ListaStock'
import { Kardex, Movimientos } from './Movimientos'

type Pestana = 'insumos' | 'productos' | 'movimientos'
type Accion = { tipo: 'merma'; item?: StockItem } | { tipo: 'ajuste' | 'kardex'; item: StockItem } | null

/** Mockup "Inventario por lotes" (docs/mockups/inventario.png). */
export function Inventario() {
  const { puede } = useSesion()
  const navegar = useNavigate()
  const celular = useEsCelular()
  const [params, setParams] = useSearchParams()
  const pestana = (['insumos', 'productos', 'movimientos'] as const).find((p) => p === params.get('pestana')) ?? 'insumos'
  const [elegido, setElegido] = useState<string>()
  const [hojaAbierta, setHojaAbierta] = useState(false)
  const [accion, setAccion] = useState<Accion>(null)
  const hoy = hoyIso()

  const stock = useQuery({ queryKey: ['inventario', 'stock'], queryFn: () => api<StockItem[]>('/inventario/stock') })
  const resumen = useQuery({
    queryKey: ['inventario', 'resumen'],
    queryFn: () => api<ResumenInventario>('/inventario/resumen'),
  })
  const todos = stock.data ?? []
  const insumos = todos.filter((s) => s.tipo_item === 'insumo')
  const productos = todos.filter((s) => s.tipo_item === 'producto')
  const lista = pestana === 'productos' ? productos : insumos
  // En escritorio siempre hay uno en el panel: el elegido o el primero de la lista.
  const actual = lista.find((s) => s.item_id === elegido) ?? (celular ? undefined : lista[0])

  function elegir(item: StockItem) {
    setElegido(item.item_id)
    if (celular) setHojaAbierta(true)
  }

  const detalle = actual && (
    <Detalle
      item={actual}
      hoy={hoy}
      alVerKardex={() => setAccion({ tipo: 'kardex', item: actual })}
      alMerma={() => setAccion({ tipo: 'merma', item: actual })}
      alAjuste={() => setAccion({ tipo: 'ajuste', item: actual })}
    />
  )

  return (
    <>
      <EncabezadoPagina
        contexto="Insumos y productos en vitrina · costo real por lote"
        titulo="Inventario"
        acciones={
          // En celular: la acción principal arriba a lo ancho y las otras dos debajo, lado a lado.
          <div className="grid w-full grid-cols-2 gap-2.5 sm:flex sm:w-auto sm:gap-3">
            {puede('inventario.merma') && (
              <Boton variante="secundario" className="max-sm:px-3 max-sm:text-[15px]" onClick={() => setAccion({ tipo: 'merma' })}>
                Registrar merma
              </Boton>
            )}
            {puede('produccion.crear') && (
              <Boton
                variante="secundario"
                className="max-sm:px-3 max-sm:text-[15px]"
                onClick={() => navegar('/compras?seccion=produccion')}
              >
                Registrar producción
              </Boton>
            )}
            {puede('compras.crear') && (
              <Boton className="col-span-2 -order-1 sm:order-none" onClick={() => navegar('/compras?seccion=nueva')}>
                Registrar compra
              </Boton>
            )}
          </div>
        }
      />

      <Indicadores resumen={resumen.data} />

      <ListaDetalle
        angosto
        lista={
          <Tarjeta className="min-w-0 px-[34px] pt-[34px] pb-6 max-lg:p-5">
            <div className="mb-6">
              <Pildoras
                etiqueta="Qué ver"
                valor={pestana}
                alCambiar={(p: Pestana) => setParams({ pestana: p })}
                opciones={[
                  { valor: 'insumos', texto: `Insumos (${insumos.length})` },
                  { valor: 'productos', texto: `Productos en vitrina (${productos.length})` },
                  { valor: 'movimientos', texto: 'Movimientos' },
                ]}
              />
            </div>
            {stock.isError && <Aviso>No pudimos cargar el inventario. Recarga la página para intentarlo de nuevo.</Aviso>}
            {pestana === 'movimientos' ? (
              <Movimientos stock={todos} />
            ) : (
              stock.isSuccess && (
                <ListaStock
                  items={lista}
                  titulo={pestana === 'productos' ? 'Productos en vitrina' : 'Insumos'}
                  seleccionado={actual?.item_id}
                  alElegir={elegir}
                  hoy={hoy}
                  celular={celular}
                />
              )
            )}
          </Tarjeta>
        }
        detalle={
          !celular && pestana !== 'movimientos' && actual ? (
            <PanelDetalle rotulo="Detalle" titulo={actual.nombre} subtitulo={resumenItem(actual)}>
              {detalle}
            </PanelDetalle>
          ) : null
        }
      />

      {celular && actual && (
        <Dialogo forma="hoja" rotulo="Detalle" titulo={actual.nombre} abierto={hojaAbierta} alCerrar={() => setHojaAbierta(false)}>
          <p className="-mt-2 mb-4 text-cafe-medio">{resumenItem(actual)}</p>
          {detalle}
        </Dialogo>
      )}

      <Dialogo
        abierto={accion?.tipo === 'merma'}
        alCerrar={() => setAccion(null)}
        titulo="Registrar merma"
      >
        {accion?.tipo === 'merma' && (
          <FormMerma items={todos} inicial={accion.item} hoy={hoy} alTerminar={() => setAccion(null)} />
        )}
      </Dialogo>
      <Dialogo
        abierto={accion?.tipo === 'ajuste'}
        alCerrar={() => setAccion(null)}
        rotulo={accion?.item?.nombre}
        titulo="Ajuste por conteo"
      >
        {accion?.tipo === 'ajuste' && <FormAjuste item={accion.item} alTerminar={() => setAccion(null)} />}
      </Dialogo>
      <Dialogo
        forma="ancho"
        abierto={accion?.tipo === 'kardex'}
        alCerrar={() => setAccion(null)}
        rotulo="Kardex"
        titulo={accion?.item?.nombre ?? ''}
      >
        {accion?.tipo === 'kardex' && <Kardex item={accion.item} />}
      </Dialogo>
    </>
  )
}
