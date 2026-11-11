import { useSearchParams } from 'react-router'
import { useSesion } from '../../auth/contexto'
import { Aviso, Pildoras } from '../../components/formulario'
import { EncabezadoPagina } from '../../components/ui'
import { MetodosPago } from './MetodosPago'
import { Negocio } from './Negocio'
import { Roles } from './Roles'
import { Sedes } from './Sedes'
import { Usuarios } from './Usuarios'

type Seccion = 'usuarios' | 'roles' | 'metodos' | 'sedes' | 'negocio'

const SECCIONES: { valor: Seccion; texto: string; permiso: string }[] = [
  { valor: 'usuarios', texto: 'Usuarios', permiso: 'usuarios.gestionar' },
  { valor: 'roles', texto: 'Roles y permisos', permiso: 'usuarios.gestionar' },
  { valor: 'metodos', texto: 'Métodos de pago', permiso: 'config.editar' },
  { valor: 'sedes', texto: 'Sedes', permiso: 'config.editar' },
  { valor: 'negocio', texto: 'Negocio', permiso: 'config.editar' },
]

export function Configuracion() {
  const { puede } = useSesion()
  const [params, setParams] = useSearchParams()
  const visibles = SECCIONES.filter((s) => puede(s.permiso))
  const pedida = params.get('seccion')
  const actual = visibles.find((s) => s.valor === pedida) ?? visibles[0]

  if (!actual) {
    return (
      <>
        <EncabezadoPagina titulo="Configuración" />
        <Aviso tono="aviso">Tu rol no incluye la configuración. Si la necesitas, pídele acceso al administrador.</Aviso>
      </>
    )
  }

  return (
    <>
      <EncabezadoPagina contexto="Usuarios, permisos y datos del negocio" titulo="Configuración" />
      <div className="mb-4">
        <Pildoras
          etiqueta="Secciones de configuración"
          opciones={visibles}
          valor={actual?.valor ?? 'usuarios'}
          alCambiar={(v) => setParams({ seccion: v })}
        />
      </div>
      {actual?.valor === 'usuarios' && <Usuarios />}
      {actual?.valor === 'roles' && <Roles />}
      {actual?.valor === 'metodos' && <MetodosPago />}
      {actual?.valor === 'sedes' && <Sedes />}
      {actual?.valor === 'negocio' && <Negocio />}
    </>
  )
}
