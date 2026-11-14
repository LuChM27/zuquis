import { useMutation, useQuery } from '@tanstack/react-query'
import { MessageCircle, Printer } from 'lucide-react'
import { useState } from 'react'
import { CampoDinero } from '../../components/CampoDinero'
import { Dialogo } from '../../components/Dialogo'
import { AreaTexto, Casilla } from '../../components/formulario'
import { TecladoPin } from '../../components/TecladoPin'
import { Boton, Campo } from '../../components/ui'
import { useAvisos } from '../../components/usarAvisos'
import { api, apiBlob, ErrorApi } from '../../lib/api'
import { calcular, montoDescuento, type LineaCarrito } from '../../lib/carrito'
import { unir } from '../../lib/clases'
import { pesos } from '../../lib/formato'
import type { Adicion, Autorizacion, Cajero, DescuentoEntrada, Venta } from '../../lib/tipos'

// --- Descuento (por ítem o por venta) -------------------------------------------------------

/** Borrador del descuento: el valor se escribe como texto para aceptar "12,5" %. */
interface BorradorDescuento {
  tipo: 'valor' | 'porcentaje'
  valor: string
  motivo: string
}

const borradorDe = (d: DescuentoEntrada | null): BorradorDescuento => ({
  tipo: d?.tipo ?? 'porcentaje',
  valor: d ? d.valor : '',
  motivo: d?.motivo ?? '',
})

/** Valida y convierte el borrador; devuelve null si está vacío o un mensaje si está mal. */
function leerDescuento(b: BorradorDescuento, base: number): DescuentoEntrada | null | string {
  const texto = b.valor.trim().replace(',', '.')
  if (!texto) return null
  if (!/^\d+(\.\d{1,4})?$/.test(texto) || Number(texto) <= 0) return 'Escribe un número mayor que cero.'
  if (b.tipo === 'porcentaje' && Number(texto) > 100) return 'El porcentaje no puede pasar de 100.'
  if (b.tipo === 'valor' && texto.includes('.')) return 'El descuento en pesos va sin decimales.'
  const d = { tipo: b.tipo, valor: texto, motivo: b.motivo.trim() }
  if (montoDescuento(base, d) > base) return `El descuento no puede pasar de ${pesos(base)}.`
  if (d.motivo.length < 3) return 'Escribe el motivo del descuento.'
  return d
}

function EditorDescuento({ borrador, alCambiar, base }: { borrador: BorradorDescuento; alCambiar: (b: BorradorDescuento) => void; base: number }) {
  const leido = leerDescuento(borrador, base)
  const monto = leido && typeof leido !== 'string' ? montoDescuento(base, leido) : 0
  return (
    <div className="grid gap-3">
      <div role="radiogroup" aria-label="Tipo de descuento" className="grid grid-cols-2 gap-1 rounded-control bg-rosa-suave p-1">
        {(['porcentaje', 'valor'] as const).map((t) => (
          <button
            key={t}
            type="button"
            role="radio"
            aria-checked={borrador.tipo === t}
            onClick={() => alCambiar({ ...borrador, tipo: t, valor: '' })}
            className={unir(
              'h-11 rounded-[10px] text-[15px]',
              borrador.tipo === t ? 'border border-dorado-borde bg-blanco font-semibold' : 'text-cafe-medio',
            )}
          >
            {t === 'porcentaje' ? 'Porcentaje (%)' : 'Valor ($)'}
          </button>
        ))}
      </div>
      <Campo
        etiqueta={borrador.tipo === 'porcentaje' ? 'Porcentaje' : 'Pesos'}
        inputMode="decimal"
        autoComplete="off"
        value={borrador.valor}
        onChange={(e) => alCambiar({ ...borrador, valor: e.target.value.replace(/[^\d.,]/g, '') })}
      />
      <Campo
        etiqueta="Motivo"
        placeholder="Cliente frecuente, producto del día anterior…"
        value={borrador.motivo}
        maxLength={200}
        onChange={(e) => alCambiar({ ...borrador, motivo: e.target.value })}
      />
      {monto > 0 && <p className="text-sm text-cafe-medio">Descuenta {pesos(monto)} de {pesos(base)}.</p>}
    </div>
  )
}

export function DialogoDescuento({
  abierto,
  alCerrar,
  base,
  actual,
  alGuardar,
}: {
  abierto: boolean
  alCerrar: () => void
  base: number
  actual: DescuentoEntrada | null
  alGuardar: (d: DescuentoEntrada | null) => void
}) {
  return (
    <Dialogo abierto={abierto} alCerrar={alCerrar} titulo="Descuento a la venta" rotulo="Venta">
      {abierto && <FormDescuento base={base} actual={actual} alGuardar={alGuardar} alCerrar={alCerrar} />}
    </Dialogo>
  )
}

function FormDescuento({ base, actual, alGuardar, alCerrar }: { base: number; actual: DescuentoEntrada | null; alGuardar: (d: DescuentoEntrada | null) => void; alCerrar: () => void }) {
  const [borrador, setBorrador] = useState(() => borradorDe(actual))
  const [intento, setIntento] = useState(false)
  const leido = leerDescuento(borrador, base)
  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        setIntento(true)
        if (typeof leido === 'string') return
        alGuardar(leido)
        alCerrar()
      }}
    >
      <EditorDescuento borrador={borrador} alCambiar={setBorrador} base={base} />
      {intento && typeof leido === 'string' && <p role="alert" className="text-sm text-peligro-texto">{leido}</p>}
      <div className="flex flex-wrap justify-end gap-3">
        {actual && (
          <Boton variante="peligro" onClick={() => { alGuardar(null); alCerrar() }}>
            Quitar descuento
          </Boton>
        )}
        <Boton type="submit">Aplicar</Boton>
      </div>
    </form>
  )
}

// --- Línea del carrito: adiciones, nota y descuento del ítem --------------------------------

export function DialogoLinea({
  linea,
  adiciones,
  alCerrar,
  alGuardar,
  alQuitar,
}: {
  linea: LineaCarrito | null
  /** Adiciones activas que ofrece el producto. */
  adiciones: Adicion[]
  alCerrar: () => void
  alGuardar: (cambios: Pick<LineaCarrito, 'adiciones' | 'nota' | 'descuento'>) => void
  alQuitar: () => void
}) {
  return (
    <Dialogo abierto={linea !== null} alCerrar={alCerrar} titulo={linea?.producto.nombre ?? ''} rotulo="Producto de la venta">
      {linea && <FormLinea linea={linea} adiciones={adiciones} alGuardar={alGuardar} alQuitar={alQuitar} alCerrar={alCerrar} />}
    </Dialogo>
  )
}

function FormLinea({
  linea,
  adiciones,
  alGuardar,
  alQuitar,
  alCerrar,
}: {
  linea: LineaCarrito
  adiciones: Adicion[]
  alGuardar: (cambios: Pick<LineaCarrito, 'adiciones' | 'nota' | 'descuento'>) => void
  alQuitar: () => void
  alCerrar: () => void
}) {
  const [elegidas, setElegidas] = useState(() => new Set(linea.adiciones.map((a) => a.id)))
  const [nota, setNota] = useState(linea.nota)
  const [conDescuento, setConDescuento] = useState(linea.descuento !== null)
  const [borrador, setBorrador] = useState(() => borradorDe(linea.descuento))
  const [intento, setIntento] = useState(false)

  const lista = adiciones.filter((a) => a.activo).map((a) => ({ id: a.id, nombre: a.nombre, precio: a.precio }))
  const nuevas = lista.filter((a) => elegidas.has(a.id))
  const bruto = calcular({
    tipoServicio: 'local',
    lineas: [{ ...linea, adiciones: nuevas, descuento: null }],
    descuento: null,
    propina: 0,
    valorDomicilio: 0,
  }).subtotal
  const leido = conDescuento ? leerDescuento(borrador, bruto) : null

  return (
    <form
      className="grid gap-5"
      onSubmit={(e) => {
        e.preventDefault()
        setIntento(true)
        if (typeof leido === 'string') return
        alGuardar({ adiciones: nuevas, nota: nota.trim(), descuento: leido })
        alCerrar()
      }}
    >
      {lista.length > 0 && (
        <fieldset>
          <legend className="mb-1 text-sm font-semibold">Adiciones (por unidad)</legend>
          {lista.map((a) => (
            <Casilla
              key={a.id}
              etiqueta={`${a.nombre} · ${pesos(a.precio)}`}
              marcada={elegidas.has(a.id)}
              alCambiar={(v) =>
                setElegidas((s) => {
                  const n = new Set(s)
                  if (v) n.add(a.id)
                  else n.delete(a.id)
                  return n
                })
              }
            />
          ))}
        </fieldset>
      )}
      <AreaTexto
        etiqueta="Nota"
        placeholder="Sin hielo, caliente, de la vitrina…"
        rows={2}
        maxLength={200}
        value={nota}
        onChange={(e) => setNota(e.target.value)}
      />
      <div>
        <Casilla etiqueta="Descuento solo a este producto" marcada={conDescuento} alCambiar={setConDescuento} />
        {conDescuento && (
          <div className="mt-2">
            <EditorDescuento borrador={borrador} alCambiar={setBorrador} base={bruto} />
          </div>
        )}
      </div>
      {intento && typeof leido === 'string' && <p role="alert" className="text-sm text-peligro-texto">{leido}</p>}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Boton variante="peligro" onClick={() => { alQuitar(); alCerrar() }}>
          Quitar de la venta
        </Boton>
        <Boton type="submit">Guardar · {pesos(bruto - (leido && typeof leido !== 'string' ? montoDescuento(bruto, leido) : 0))}</Boton>
      </div>
    </form>
  )
}

// --- Propina --------------------------------------------------------------------------------

export function DialogoPropina({ abierto, alCerrar, actual, alGuardar }: { abierto: boolean; alCerrar: () => void; actual: number; alGuardar: (v: number) => void }) {
  return (
    <Dialogo abierto={abierto} alCerrar={alCerrar} titulo="Propina" rotulo="Aparte, no es venta">
      {abierto && <FormPropina actual={actual} alGuardar={alGuardar} alCerrar={alCerrar} />}
    </Dialogo>
  )
}

function FormPropina({ actual, alGuardar, alCerrar }: { actual: number; alGuardar: (v: number) => void; alCerrar: () => void }) {
  const [valor, setValor] = useState<number | null>(actual || null)
  return (
    <form
      className="grid gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        alGuardar(valor ?? 0)
        alCerrar()
      }}
    >
      <p className="text-sm text-cafe-medio">Se cobra con la venta, pero va aparte en la caja: no cuenta como venta.</p>
      <CampoDinero etiqueta="Valor de la propina" valor={valor} alCambiar={setValor} />
      <div className="flex justify-end gap-3">
        {actual > 0 && (
          <Boton variante="peligro" onClick={() => { alGuardar(0); alCerrar() }}>
            Quitar propina
          </Boton>
        )}
        <Boton type="submit">Aplicar</Boton>
      </div>
    </form>
  )
}

// --- Autorización de un descuento por encima del tope del rol -------------------------------

export function DialogoAutorizacion({
  abierto,
  alCerrar,
  alAutorizar,
  error,
  ocupado,
}: {
  abierto: boolean
  alCerrar: () => void
  alAutorizar: (a: Autorizacion) => void
  error?: string
  ocupado: boolean
}) {
  return (
    <Dialogo abierto={abierto} alCerrar={alCerrar} titulo="Autorizar descuento" rotulo="Supera el tope de tu rol">
      {abierto && <FormAutorizacion alAutorizar={alAutorizar} error={error} ocupado={ocupado} />}
    </Dialogo>
  )
}

function FormAutorizacion({ alAutorizar, error, ocupado }: { alAutorizar: (a: Autorizacion) => void; error?: string; ocupado: boolean }) {
  const [modo, setModo] = useState<'pin' | 'clave'>('pin')
  const [quien, setQuien] = useState<Cajero | null>(null)
  const [pin, setPin] = useState('')
  const [email, setEmail] = useState('')
  const [clave, setClave] = useState('')
  const cajeros = useQuery({ queryKey: ['cajeros'], queryFn: () => api<Cajero[]>('/auth/cajeros') })

  return (
    <div className="grid gap-4">
      <p className="text-sm text-cafe-medio">Un administrador aprueba el descuento con su PIN o su contraseña. Queda registrado quién autorizó.</p>
      <div role="radiogroup" aria-label="Cómo autoriza" className="grid grid-cols-2 gap-1 rounded-control bg-rosa-suave p-1">
        {(['pin', 'clave'] as const).map((m) => (
          <button
            key={m}
            type="button"
            role="radio"
            aria-checked={modo === m}
            onClick={() => setModo(m)}
            className={unir('h-11 rounded-[10px] text-[15px]', modo === m ? 'border border-dorado-borde bg-blanco font-semibold' : 'text-cafe-medio')}
          >
            {m === 'pin' ? 'Con PIN' : 'Con contraseña'}
          </button>
        ))}
      </div>
      {modo === 'pin' && !quien && (
        <ul className="grid gap-2">
          {(cajeros.data ?? []).map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => setQuien(c)}
                className="flex h-12 w-full items-center rounded-control border border-dorado-claro bg-crema px-4 text-left font-semibold hover:border-dorado-borde"
              >
                {c.nombre}
              </button>
            </li>
          ))}
          {cajeros.isSuccess && cajeros.data.length === 0 && <li className="text-sm text-cafe-medio">Nadie tiene PIN todavía: usa la contraseña.</li>}
        </ul>
      )}
      {modo === 'pin' && quien && (
        <div>
          <p className="mb-3 text-center font-semibold">{quien.nombre}</p>
          <TecladoPin
            valor={pin}
            alCambiar={setPin}
            alEnviar={() => {
              alAutorizar({ usuario_id: quien.id, pin })
              setPin('')
            }}
            ocupado={ocupado}
            error={error}
            textoEnviar="Autorizar"
          />
          <button type="button" onClick={() => setQuien(null)} className="mt-3 text-[15px] font-semibold text-fucsia hover:underline">
            Elegir otra persona
          </button>
        </div>
      )}
      {modo === 'clave' && (
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (email && clave) alAutorizar({ email, clave })
          }}
        >
          <Campo etiqueta="Correo de quien autoriza" type="email" autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} />
          <Campo etiqueta="Contraseña" type="password" autoComplete="off" value={clave} onChange={(e) => setClave(e.target.value)} error={error} />
          <Boton type="submit" disabled={!email || !clave || ocupado}>
            Autorizar y cobrar
          </Boton>
        </form>
      )}
    </div>
  )
}

// --- Venta registrada: cambio, comprobante y compartir --------------------------------------

function textoComprobante(v: Venta): string {
  const lineas = v.items.map((i) => `${Number(i.cantidad)} × ${i.producto}: ${pesos(i.subtotal)}`)
  return [
    `Zuqui's Repostería · Venta n.º ${String(v.numero).padStart(4, '0')}`,
    ...lineas,
    v.descuento_total ? `Descuento: −${pesos(v.descuento_total)}` : null,
    `Total: ${pesos(v.total)}`,
    v.propina ? `Propina: ${pesos(v.propina)}` : null,
    v.valor_domicilio ? `Domicilio: ${pesos(v.valor_domicilio)}` : null,
    '¡Gracias por tu compra!',
  ]
    .filter(Boolean)
    .join('\n')
}

export function VentaRegistrada({ venta, alCerrar }: { venta: Venta | null; alCerrar: () => void }) {
  const { avisar } = useAvisos()
  const pdf = useMutation({
    mutationFn: async () => apiBlob(`/ventas/${venta!.id}/comprobante`),
    onError: (e) => avisar(e instanceof ErrorApi ? e.message : 'No se pudo generar el comprobante.', 'error'),
  })

  async function imprimir() {
    const blob = await pdf.mutateAsync().catch(() => null)
    if (!blob) return
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  }

  async function compartir() {
    const v = venta!
    const texto = textoComprobante(v)
    const blob = await pdf.mutateAsync().catch(() => null)
    const archivo = blob ? new File([blob], `venta-${v.numero}.pdf`, { type: 'application/pdf' }) : null
    // En el celular se comparte el PDF (WhatsApp lo ofrece); si no se puede, va el texto.
    if (archivo && navigator.canShare?.({ files: [archivo] })) {
      try {
        await navigator.share({ files: [archivo], text: texto })
        return
      } catch {
        return
      }
    }
    window.open(`https://wa.me/?text=${encodeURIComponent(texto)}`, '_blank', 'noopener')
  }

  const numero = venta ? String(venta.numero).padStart(4, '0') : ''
  return (
    <Dialogo abierto={venta !== null} alCerrar={alCerrar} titulo={`Venta n.º ${numero}`} rotulo="Venta registrada">
      {venta && (
        <div className="grid gap-5">
          <dl className="grid gap-2 text-[15px]">
            <div className="flex justify-between">
              <dt className="text-cafe-medio">Cobrado</dt>
              <dd className="font-semibold">{pesos(venta.cobrado)}</dd>
            </div>
            {venta.pagos.map((p) => (
              <div key={p.metodo_pago_id} className="flex justify-between">
                <dt className="text-cafe-medio">{p.metodo}</dt>
                <dd>{pesos(p.monto)}</dd>
              </div>
            ))}
          </dl>
          {venta.cambio > 0 && (
            <div className="rounded-control bg-exito-fondo p-4 text-center text-exito-texto">
              <p className="text-sm font-semibold">Cambio para entregar</p>
              <p className="font-serif text-[44px] leading-none font-semibold">{pesos(venta.cambio)}</p>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <Boton variante="secundario" onClick={() => void imprimir()} disabled={pdf.isPending}>
              <Printer aria-hidden className="size-5" strokeWidth={1.7} />
              Imprimir
            </Boton>
            <Boton variante="secundario" onClick={() => void compartir()} disabled={pdf.isPending}>
              <MessageCircle aria-hidden className="size-5" strokeWidth={1.7} />
              Compartir
            </Boton>
          </div>
          <Boton onClick={alCerrar} autoFocus>
            Nueva venta
          </Boton>
        </div>
      )}
    </Dialogo>
  )
}
