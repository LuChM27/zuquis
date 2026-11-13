import { useQuery } from '@tanstack/react-query'
import {
  Cake,
  CakeSlice,
  Candy,
  Coffee,
  Cookie,
  Croissant,
  CupSoda,
  GlassWater,
  IceCreamCone,
  Milk,
  Pizza,
  Plus,
  Salad,
  Sandwich,
  Soup,
  Wine,
  type LucideIcon,
} from 'lucide-react'
import { apiBlob } from '../../lib/api'

/** Íconos que se pueden elegir para una categoría (se guarda la clave en kebab-case). */
export const ICONOS: Record<string, { icono: LucideIcon; nombre: string }> = {
  croissant: { icono: Croissant, nombre: 'Croissant' },
  sandwich: { icono: Sandwich, nombre: 'Sándwich' },
  salad: { icono: Salad, nombre: 'Ensalada' },
  'ice-cream-cone': { icono: IceCreamCone, nombre: 'Helado' },
  coffee: { icono: Coffee, nombre: 'Café' },
  'glass-water': { icono: GlassWater, nombre: 'Vaso' },
  'cup-soda': { icono: CupSoda, nombre: 'Gaseosa' },
  milk: { icono: Milk, nombre: 'Leche' },
  'cake-slice': { icono: CakeSlice, nombre: 'Porción de torta' },
  cake: { icono: Cake, nombre: 'Torta' },
  cookie: { icono: Cookie, nombre: 'Galleta' },
  candy: { icono: Candy, nombre: 'Dulce' },
  pizza: { icono: Pizza, nombre: 'Pizza' },
  soup: { icono: Soup, nombre: 'Sopa' },
  wine: { icono: Wine, nombre: 'Copa' },
  plus: { icono: Plus, nombre: 'Adición' },
}


/**
 * Foto protegida (necesita el token): se descarga como Blob y se muestra con una URL local.
 * La URL queda en la caché de consultas (una por foto) mientras dure la sesión.
 */
export function useImagen(url: string | null): string | undefined {
  const local = useQuery({
    queryKey: ['archivo', url],
    queryFn: async () => URL.createObjectURL(await apiBlob(url!)),
    enabled: !!url,
    staleTime: Infinity,
  })
  return url ? local.data : undefined
}

/** Mueve el elemento de `desde` a `hasta` y devuelve la lista nueva. */
export function mover<T>(lista: T[], desde: number, hasta: number): T[] {
  const copia = [...lista]
  const [x] = copia.splice(desde, 1)
  copia.splice(hasta, 0, x)
  return copia
}
