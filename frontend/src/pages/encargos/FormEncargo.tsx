import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Buscador } from '../../components/Buscador'
import { CampoDinero } from '../../components/CampoDinero'
import { Dialogo } from '../../components/Dialogo'
import { AreaTexto, Aviso } from '../../components/formulario'
import { Boton, Campo } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api, ErrorApi } from '../../lib/api'
import { unir } from '../../lib/clases'
import { aPesos, dec } from '../../lib/decimal'
import { pesos } from '../../lib/formato'
import { useClaveIdempotencia } from '../../lib/idempotencia'
import type { Encargo, Producto, TipoEntrega } from '../../lib/tipos'
import { useCaja } from '../caja/usarCaja'
import { useMetodosActivos } from '../clientes/datos'
import { SelectorCliente } from '../clientes/SelectorCliente'
import { diaLocal, entregaIso, horaLocal } from './fechas'

interface Item {
  clave: string
  productoId: string
  descripcion: string
  cantidad: string
  precio: number | null
}

let consecutivo = 0
const itemVacio = (): Item => ({ clave: `i${++consecutivo}`, productoId: '', descripcion: '', cantidad: '1', precio: null })
const cantidadValida = (c: string) => /^\d+([.,]\d{1,3})?$/.test(c.trim()) && dec(c.trim().replace(',', '.')).gt(0)

function subtotalItem(i: Item): number {
  if (!cantidadValida(i.cantidad) || i.precio === null) return 0
  return aPesos(dec(i.cantidad.trim().replace(',', '.')).mul(i.precio))
}

/** Nuevo encargo o edición de uno pendiente (RF-34). El abono inicial es opcional. */
export function DialogoEncargo({
  abierto,
  encargo,
  diaInicial,
  alCerrar,
  alGuardar,
}: {
  abierto: boolean
  encargo?: Encargo | null
  diaInicial: string
  alCerrar: () => void
  alGuardar: (e: Encargo) => void
}) {
  return (
    <Dialogo abierto={abierto} alCerrar={alCerrar} forma="ancho" titulo={encargo ? 'Editar encargo' : 'Nuevo encargo'} rotulo={encargo ? `Encargo n.º ${String(encargo.numero).padStart(4, '0')}` : undefined}>
      <FormEncargo key={encargo?.id ?? diaInicial} encargo={encargo} diaInicial={diaInicial} alGuardar={alGuardar} alCancelar={alCerrar} />
    </Dialogo>
  )
}

function FormEncargo({
  encargo,
  diaInicial,
  alGuardar,
  alCancelar,
}: {
  encargo?: Encargo | null
  diaInicial: string
  alGuardar: (e: Encargo) => void
  alCancelar: () => void
}) {
  const { avisar } = useAvisos()
  const clienteQuery = useQueryClient()
  const clave = useClaveIdempotencia()
  const caja = useCaja()
  const metodos = useMetodosActivos()
  const productos = useQuery({ queryKey: ['productos', 'activos'], queryFn: () => api<Producto[]>('/productos') })

  const [clienteId, setClienteId] = useState(encargo?.cliente.id ?? '')
  const [direccionCliente, setDireccionCliente] = useState(encargo?.cliente.direccion ?? '')
  const [dia, setDia] = useState(encargo ? diaLocal(encargo.fecha_entrega) : diaInicial)
  const [hora, setHora] = useState(encargo ? horaLocal(encargo.fecha_entrega) : '17:00')
  const [tipo, setTipo] = useState<TipoEntrega>(encargo?.tipo_entrega ?? 'recoge')
  const [direccion, setDireccion] = useState(encargo?.direccion_entrega ?? '')
  const [descripcion, setDescripcion] = useState(encargo?.descripcion ?? '')
  const [observaciones, setObservaciones] = useState(encargo?.observaciones ?? '')
  const [items, setItems] = useState<Item[]>(() =>
    encargo
      ? encargo.items.map((i) => ({ clave: i.id, productoId: i.producto_id ?? '', descripcion: i.descripcion, cantidad: dec(i.cantidad).toFixed(), precio: i.precio }))
      : [itemVacio()],
  )
  const [abono, setAbono] = useState<number | null>(null)
  const [metodoAbono, setMetodoAbono] = useState('')
  const [intento, setIntento] = useState(false)

  const total = items.reduce((s, i) => s + subtotalItem(i), 0)
  const itemsMal = items.some((i) => !cantidadValida(i.cantidad) || i.precio === null || (!i.productoId && !i.descripcion.trim()))
  const errores = {
    cliente: !clienteId ? 'Elige el cliente.' : undefined,
    fecha: !dia || !hora ? 'Indica fecha y hora.' : undefined,
    direccion: tipo === 'domicilio' && !direccion.trim() && !direccionCliente ? 'Escribe la dirección de entrega.' : undefined,
    items: itemsMal ? 'Cada ítem necesita descripción, cantidad y precio.' : total <= 0 ? 'El encargo debe valer más de $0.' : undefined,
    abono: abono ? (abono > total ? 'El abono no puede superar el total.' : !metodoAbono ? 'Elige cómo pagó el abono.' : undefined) : undefined,
  }
  const valido = Object.values(errores).every((e) => !e)

  const guardar = useMutation({
    mutationFn: () => {
      const cuerpo = {
        cliente_id: clienteId,
        descripcion: descripcion.trim() || null,
        fecha_entrega: entregaIso(dia, hora),
        tipo_entrega: tipo,
        direccion_entrega: tipo === 'domicilio' ? direccion.trim() || null : null,
        observaciones: observaciones.trim() || null,
        items: items.map((i) => ({
          producto_id: i.productoId || null,
          descripcion: i.descripcion.trim() || null,
          cantidad: i.cantidad.trim().replace(',', '.'),
          precio: i.precio,
        })),
      }
      if (encargo) return api<Encargo>(`/encargos/${encargo.id}`, { method: 'PATCH', json: cuerpo })
      const conAbono = { ...cuerpo, abono: abono ? { monto: abono, metodo_pago_id: metodoAbono } : null }
      return api<Encargo>('/encargos', { method: 'POST', json: conAbono, idempotencia: clave.para(conAbono) })
    },
    onSuccess: (e) => {
      clave.olvidar()
      for (const k of [['encargos'], ['caja'], ['clientes']]) void clienteQuery.invalidateQueries({ queryKey: k })
      avisar(encargo ? 'Encargo actualizado.' : `Encargo n.º ${String(e.numero).padStart(4, '0')} creado.`)
      alGuardar(e)
    },
  })

  const opcionesProducto = [
    { valor: '', texto: 'Personalizado (sin producto de la carta)' },
    ...(productos.data ?? []).filter((p) => p.activo).map((p) => ({ valor: p.id, texto: p.nombre, detalle: pesos(p.precio) })),
  ]
  const cambiarItem = (clave: string, cambio: Partial<Item>) => setItems((l) => l.map((i) => (i.clave === clave ? { ...i, ...cambio } : i)))

  return (
    <form
      noValidate
      className="grid gap-5"
      onSubmit={(e) => {
        e.preventDefault()
        setIntento(true)
        if (valido) guardar.mutate()
      }}
    >
      <SelectorCliente
        valor={clienteId}
        alCambiar={(c) => {
          setClienteId(c?.id ?? '')
          setDireccionCliente(c?.direccion ?? '')
          if (c?.direccion && !direccion) setDireccion(c.direccion)
        }}
        error={intento ? errores.cliente : undefined}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Campo etiqueta="Fecha de entrega" type="date" value={dia} onChange={(e) => setDia(e.target.value)} error={intento ? errores.fecha : undefined} />
        <Campo etiqueta="Hora de entrega" type="time" value={hora} onChange={(e) => setHora(e.target.value)} />
      </div>

      <div>
        <div role="radiogroup" aria-label="Tipo de entrega" className="grid grid-cols-2 gap-1 rounded-[14px] bg-rosa-suave p-1">
          {(
            [
              ['recoge', 'Recoge en el local'],
              ['domicilio', 'Domicilio'],
            ] as const
          ).map(([v, t]) => (
            <button
              key={v}
              type="button"
              role="radio"
              aria-checked={tipo === v}
              onClick={() => setTipo(v)}
              className={unir('h-12 rounded-[11px] text-[16px]', tipo === v ? 'border border-dorado-borde bg-blanco font-semibold' : 'hover:bg-blanco/50')}
            >
              {t}
            </button>
          ))}
        </div>
        {tipo === 'domicilio' && (
          <Campo
            className="mt-3"
            etiqueta="Dirección de entrega"
            value={direccion}
            maxLength={200}
            placeholder={direccionCliente || undefined}
            onChange={(e) => setDireccion(e.target.value)}
            error={intento ? errores.direccion : undefined}
          />
        )}
      </div>

      <fieldset>
        <legend className="mb-2 text-sm font-semibold">Qué lleva</legend>
        <ul className="grid gap-3">
          {items.map((i, n) => (
            <li key={i.clave} aria-label={`Ítem ${n + 1}`} className="grid gap-3 rounded-[14px] border border-linea p-3 sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1.3fr)_90px_140px_auto] sm:items-end">
              <Buscador
                etiqueta="Producto"
                opciones={opcionesProducto}
                valor={i.productoId}
                alCambiar={(id) => {
                  const p = productos.data?.find((x) => x.id === id)
                  cambiarItem(i.clave, p ? { productoId: id, descripcion: p.nombre, precio: p.precio } : { productoId: '' })
                }}
              />
              <Campo etiqueta="Descripción" value={i.descripcion} maxLength={200} onChange={(e) => cambiarItem(i.clave, { descripcion: e.target.value })} />
              <Campo etiqueta="Cantidad" inputMode="decimal" value={i.cantidad} onChange={(e) => cambiarItem(i.clave, { cantidad: e.target.value })} />
              <CampoDinero etiqueta="Precio c/u" valor={i.precio} alCambiar={(v) => cambiarItem(i.clave, { precio: v })} />
              <button
                type="button"
                disabled={items.length === 1}
                onClick={() => setItems((l) => l.filter((x) => x.clave !== i.clave))}
                aria-label={`Quitar el ítem ${n + 1}`}
                className="grid size-12 place-items-center rounded-control border border-dorado-claro hover:border-dorado-borde disabled:opacity-40"
              >
                <Trash2 aria-hidden className="size-5" strokeWidth={1.7} />
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <Boton variante="secundario" className="h-11" onClick={() => setItems((l) => [...l, itemVacio()])}>
            <Plus aria-hidden className="size-5" />
            Agregar ítem
          </Boton>
          <p className="text-[17px]">
            Valor total <strong className="ml-2 font-serif text-[28px]">{pesos(total)}</strong>
          </p>
        </div>
        {intento && errores.items && <p role="alert" className="mt-2 text-sm text-peligro-texto">{errores.items}</p>}
      </fieldset>

      <Campo etiqueta="Título del encargo (opcional)" placeholder="Se arma con los ítems" value={descripcion} maxLength={200} onChange={(e) => setDescripcion(e.target.value)} />
      <AreaTexto etiqueta="Observaciones" value={observaciones} maxLength={500} onChange={(e) => setObservaciones(e.target.value)} />

      {!encargo && (
        <fieldset className="grid gap-3 rounded-[14px] border border-linea p-4">
          <legend className="px-1 text-sm font-semibold">Abono inicial (opcional)</legend>
          {caja.data?.abierta ? (
            <>
              <CampoDinero etiqueta="Valor del abono" valor={abono} alCambiar={setAbono} error={intento && abono && abono > total ? errores.abono : undefined} />
              {abono ? (
                <div role="radiogroup" aria-label="Cómo pagó el abono" className="flex flex-wrap gap-2">
                  {(metodos.data ?? []).map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      role="radio"
                      aria-checked={metodoAbono === m.id}
                      onClick={() => setMetodoAbono(m.id)}
                      className={unir('h-11 rounded-control border px-4 text-[15px]', metodoAbono === m.id ? 'border-fucsia bg-rosa-suave font-semibold text-fucsia-oscuro' : 'border-dorado-claro bg-blanco')}
                    >
                      {m.nombre}
                    </button>
                  ))}
                </div>
              ) : null}
              {intento && abono && !metodoAbono ? <p role="alert" className="text-sm text-peligro-texto">{errores.abono}</p> : null}
            </>
          ) : (
            <p className="text-sm text-cafe-medio">La caja está cerrada: el abono se puede registrar después, con la caja abierta.</p>
          )}
        </fieldset>
      )}

      {guardar.isError && <Aviso>{guardar.error instanceof ErrorApi ? guardar.error.message : 'No se pudo guardar.'}</Aviso>}
      <div className="flex flex-wrap justify-end gap-3">
        <Boton variante="secundario" onClick={alCancelar}>
          Cancelar
        </Boton>
        <Boton type="submit" disabled={guardar.isPending}>
          {guardar.isPending ? 'Guardando…' : encargo ? 'Guardar cambios' : 'Crear encargo'}
        </Boton>
      </div>
    </form>
  )
}
