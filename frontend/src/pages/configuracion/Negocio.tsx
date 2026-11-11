import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Aviso, Interruptor } from '../../components/formulario'
import { Boton, Campo, Tarjeta, TituloTarjeta } from '../../components/ui'
import { api } from '../../lib/api'
import type { Configuracion, Rol } from '../../lib/tipos'
import { useGuardar, vacioANulo } from './acciones'

/** "10.0000" → "10"; "12.5000" → "12,5"; "0" → "0" */
const mostrarPct = (v: string) =>
  (v.includes('.') ? v.replace(/0+$/, '').replace(/\.$/, '') : v).replace('.', ',')

export function Negocio() {
  const config = useQuery({ queryKey: ['configuracion'], queryFn: () => api<Configuracion>('/configuracion') })
  const roles = useQuery({ queryKey: ['roles'], queryFn: () => api<Rol[]>('/roles') })

  if (config.isError || roles.isError) {
    return <Aviso>No pudimos cargar la configuración. Recarga la página para intentarlo de nuevo.</Aviso>
  }
  if (!config.data || !roles.data) return null
  return <FormNegocio config={config.data} roles={roles.data.filter((r) => r.activo)} />
}

function FormNegocio({ config, roles }: { config: Configuracion; roles: Rol[] }) {
  const n = config.negocio
  const [nombre, setNombre] = useState(n.nombre)
  const [nit, setNit] = useState(n.nit ?? '')
  const [direccion, setDireccion] = useState(n.direccion ?? '')
  const [telefono, setTelefono] = useState(n.telefono ?? '')
  const [dias, setDias] = useState(String(config.dias_alerta_vencimiento))
  const [sinStock, setSinStock] = useState(config.permitir_venta_sin_stock)
  const [topes, setTopes] = useState<Record<string, string>>(() =>
    Object.fromEntries(roles.map((r) => [r.id, mostrarPct(config.tope_descuento_por_rol[r.id] ?? '0')])),
  )
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [guardado, setGuardado] = useState(false)

  const guardar = useGuardar(
    (cambios: Partial<Configuracion>) => api<Configuracion>('/configuracion', { method: 'PATCH', json: cambios }),
    [['configuracion']],
    () => setGuardado(true),
  )

  function enviar(ev: FormEvent) {
    ev.preventDefault()
    const e: Record<string, string> = {}
    if (nombre.trim().length < 2) e.nombre = 'Escribe el nombre del negocio.'
    if (!/^\d+$/.test(dias) || Number(dias) > 60) e.dias = 'Escribe un número de días entre 0 y 60.'
    // Se parte de los topes guardados para no perder los de roles inactivos.
    const topesApi: Record<string, string> = { ...config.tope_descuento_por_rol }
    for (const r of roles) {
      const t = (topes[r.id] ?? '0').replace(',', '.').trim() || '0'
      if (!/^\d{1,3}(\.\d{1,2})?$/.test(t) || Number(t) > 100) e[`tope-${r.id}`] = 'Entre 0 y 100.'
      else topesApi[r.id] = t
    }
    setErrores(e)
    if (Object.keys(e).length) return
    setGuardado(false)
    guardar.mutate({
      negocio: { ...n, nombre: nombre.trim(), nit: vacioANulo(nit), direccion: vacioANulo(direccion), telefono: vacioANulo(telefono) },
      dias_alerta_vencimiento: Number(dias),
      permitir_venta_sin_stock: sinStock,
      tope_descuento_por_rol: topesApi,
    })
  }

  return (
    <form onSubmit={enviar} noValidate className="grid items-start gap-4 lg:grid-cols-2">
      <Tarjeta>
        <TituloTarjeta>Datos del negocio</TituloTarjeta>
        <p className="mt-1 text-sm text-cafe-suave">Salen en los comprobantes y en los reportes.</p>
        <div className="mt-5 flex flex-col gap-4">
          <Campo etiqueta="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} error={errores.nombre} />
          <Campo etiqueta="NIT" value={nit} onChange={(e) => setNit(e.target.value)} placeholder="Opcional" />
          <Campo etiqueta="Dirección" value={direccion} onChange={(e) => setDireccion(e.target.value)} />
          <Campo etiqueta="Teléfono" type="tel" inputMode="tel" value={telefono} onChange={(e) => setTelefono(e.target.value)} />
        </div>
      </Tarjeta>

      <div className="flex flex-col gap-4">
        <Tarjeta>
          <TituloTarjeta>Operación</TituloTarjeta>
          <div className="mt-5 flex flex-col gap-5">
            <Campo
              etiqueta="Avisar vencimientos con estos días de anticipación"
              inputMode="numeric"
              value={dias}
              onChange={(e) => setDias(e.target.value.trim())}
              error={errores.dias}
              className="max-w-[260px]"
            />
            <Interruptor
              etiqueta="Permitir vender sin stock registrado"
              ayuda="Lo que falte queda como faltante por regularizar; el stock nunca queda negativo."
              activo={sinStock}
              alCambiar={setSinStock}
            />
          </div>
        </Tarjeta>

        <Tarjeta>
          <TituloTarjeta>Tope de descuento por rol</TituloTarjeta>
          <p className="mt-1 text-sm text-cafe-suave">Por encima del tope, el descuento necesita autorización.</p>
          <ul className="mt-3 divide-y divide-linea">
            {roles.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-4 py-2.5">
                <span>{r.nombre}</span>
                <span className="flex items-center gap-2">
                  <input
                    aria-label={`Tope de descuento de ${r.nombre}, en porcentaje`}
                    aria-invalid={errores[`tope-${r.id}`] ? true : undefined}
                    inputMode="decimal"
                    value={topes[r.id] ?? '0'}
                    onChange={(e) => setTopes((t) => ({ ...t, [r.id]: e.target.value }))}
                    className={`h-11 w-20 rounded-control border bg-blanco px-3 text-right focus:border-dorado-borde focus:outline-none ${errores[`tope-${r.id}`] ? 'border-peligro' : 'border-dorado-claro'}`}
                  />
                  <span className="text-cafe-suave">%</span>
                </span>
              </li>
            ))}
          </ul>
          {Object.keys(errores).some((k) => k.startsWith('tope-')) && (
            <p className="mt-1 text-sm text-peligro-texto">Cada tope debe ser un porcentaje entre 0 y 100.</p>
          )}
        </Tarjeta>

        <Aviso tono="aviso">
          Los impuestos y la facturación electrónica están desactivados hasta que el contador defina el régimen tributario.
        </Aviso>

        {guardar.error && <Aviso>{guardar.error}</Aviso>}
        <div className="flex flex-col gap-2">
          <Boton type="submit" disabled={guardar.isPending} className="w-full">
            {guardar.isPending ? 'Guardando…' : 'Guardar configuración'}
          </Boton>
          <p role="status" className="min-h-5 text-center text-sm font-semibold text-exito-texto">
            {guardado && 'Cambios guardados'}
          </p>
        </div>
      </div>
    </form>
  )
}
