import { CakeSlice } from 'lucide-react'
import { ICONOS } from './utilidades'

export function IconoCategoria({ icono, className }: { icono: string | null; className?: string }) {
  const Icono = (icono && ICONOS[icono]?.icono) || CakeSlice
  return <Icono aria-hidden className={className ?? 'size-5'} strokeWidth={1.7} />
}
