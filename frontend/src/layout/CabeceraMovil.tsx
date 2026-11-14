import { Menu, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router'
import { Marca } from './Marca'
import { NavegacionPrincipal, TarjetaUsuario } from './BarraLateral'
import { useCaja } from '../pages/caja/usarCaja'
import { SECCIONES } from './navegacion'

/** Cabecera rosa del mockup de celular: logo, título de la sección y menú. */
export function CabeceraMovil() {
  const [abierto, setAbierto] = useState(false)
  const { pathname } = useLocation()
  const boton = useRef<HTMLButtonElement>(null)
  const caja = useCaja()
  const conCaja = pathname.startsWith('/vender') || pathname.startsWith('/caja')
  const seccion =
    SECCIONES.find((s) => s.ruta !== '/' && pathname.startsWith(s.ruta)) ??
    SECCIONES.find((s) => s.ruta === pathname)

  useEffect(() => {
    if (!abierto) return
    const alTeclear = (e: KeyboardEvent) => e.key === 'Escape' && setAbierto(false)
    document.addEventListener('keydown', alTeclear)
    document.body.style.overflow = 'hidden'
    const disparador = boton.current
    return () => {
      document.removeEventListener('keydown', alTeclear)
      document.body.style.overflow = ''
      disparador?.focus()
    }
  }, [abierto])

  return (
    <>
      <header className="sticky top-0 z-20 flex h-20 items-center gap-3 bg-rosa px-4 lg:hidden">
        <img src="/logo.png" alt="Zuqui's" className="size-[46px] rounded-full" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-serif text-[30px] leading-none font-semibold">{seccion?.nombre ?? "Zuqui's"}</p>
          {conCaja && caja.data && (
            <p className="mt-1 flex items-center gap-1.5 text-sm font-semibold">
              <span aria-hidden className={`size-2 rounded-full ${caja.data.abierta ? 'bg-exito' : 'bg-cafe-suave'}`} />
              <span className={caja.data.abierta ? 'text-exito-texto' : 'text-cafe-medio'}>
                {caja.data.abierta ? 'Caja abierta' : 'Caja cerrada'}
              </span>
            </p>
          )}
        </div>
        <button
          ref={boton}
          type="button"
          onClick={() => setAbierto(true)}
          aria-label="Abrir menú"
          aria-expanded={abierto}
          className="grid size-11 place-items-center rounded-control border border-dorado-claro bg-crema"
        >
          <Menu aria-hidden className="size-6" strokeWidth={1.8} />
        </button>
      </header>

      {abierto && (
        <div className="fixed inset-0 z-30 lg:hidden" role="dialog" aria-modal="true" aria-label="Menú">
          <button
            type="button"
            aria-label="Cerrar menú"
            className="absolute inset-0 bg-cafe/30"
            onClick={() => setAbierto(false)}
          />
          <div className="absolute inset-y-0 left-0 flex w-[min(300px,85vw)] flex-col bg-rosa px-[19px] pt-[27px] pb-[19px] shadow-xl">
            <div className="flex items-start justify-between">
              <Marca />
              <button
                type="button"
                autoFocus
                onClick={() => setAbierto(false)}
                aria-label="Cerrar menú"
                className="-mt-2 -mr-2 grid size-11 place-items-center rounded-control"
              >
                <X aria-hidden className="size-6" strokeWidth={1.8} />
              </button>
            </div>
            <div className="mt-[23px] min-h-0 flex-1 overflow-y-auto">
              <NavegacionPrincipal alElegir={() => setAbierto(false)} />
            </div>
            <TarjetaUsuario />
          </div>
        </div>
      )}
    </>
  )
}
