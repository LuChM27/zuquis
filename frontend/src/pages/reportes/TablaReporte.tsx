import { Tarjeta, TituloTarjeta } from '../../components/ui'
import { unir } from '../../lib/clases'
import { pesos } from '../../lib/formato'
import type { Columna, Fila, Seccion, TipoColumna } from '../../lib/reportes'
import { fechaIso } from '../../lib/unidades'

const NUMERICOS: TipoColumna[] = ['pesos', 'cantidad', 'porcentaje', 'entero']

function sinCeros(texto: string): string {
  return texto.includes('.') ? texto.replace(/0+$/, '').replace(/\.$/, '') : texto
}

/** Texto de una celda según el tipo de su columna (o el `_tipo` de la fila, en el resumen). */
function celda(valor: Fila[string] | undefined, tipo: TipoColumna): string {
  if (valor === null || valor === undefined || valor === '') return ''
  switch (tipo) {
    case 'pesos':
      return pesos(valor as number)
    case 'porcentaje':
      return `${sinCeros(String(valor)).replace('.', ',')} %`
    case 'cantidad':
      return sinCeros(String(valor)).replace('.', ',')
    case 'entero':
      return new Intl.NumberFormat('es-CO').format(Number(valor))
    case 'fecha': {
      const texto = String(valor)
      return /^\d{4}-\d{2}-\d{2}$/.test(texto.slice(0, 10)) && texto.length === 10
        ? fechaIso(texto)
        : new Intl.DateTimeFormat('es-CO', { timeZone: 'America/Bogota', day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(texto))
    }
    default:
      return String(valor)
  }
}

function tipoDe(c: Columna, f: Fila): TipoColumna {
  return c.clave === 'valor' && typeof f._tipo === 'string' ? (f._tipo as TipoColumna) : c.tipo
}

function Valor({ valor, tipo }: { valor: Fila[string] | undefined; tipo: TipoColumna }) {
  const negativo = tipo === 'pesos' && typeof valor === 'number' && valor < 0
  return <span className={unir('tabular-nums', negativo && 'text-peligro-texto')}>{celda(valor, tipo)}</span>
}

/** Una sección de un reporte: tabla en pantallas anchas y tarjetas apiladas en celular. */
export function TablaReporte({ seccion }: { seccion: Seccion }) {
  const { columnas, filas, totales } = seccion
  return (
    <Tarjeta className="p-5">
      <TituloTarjeta className="mb-4 text-[24px]">{seccion.titulo}</TituloTarjeta>
      {filas.length === 0 ? (
        <p className="text-cafe-suave">Sin datos en este rango</p>
      ) : (
        <>
          <div className="-mx-5 hidden overflow-x-auto px-5 sm:block">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-dorado-claro">
                  {columnas.map((c) => (
                    <th
                      key={c.clave}
                      scope="col"
                      className={unir(
                        'px-3 pb-3 text-[13px] font-semibold tracking-[0.08em] whitespace-nowrap text-cafe-suave uppercase',
                        NUMERICOS.includes(c.tipo) && 'text-right',
                      )}
                    >
                      {c.titulo}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filas.map((f, i) => (
                  <tr key={i} className="border-b border-linea">
                    {columnas.map((c) => (
                      <td key={c.clave} className={unir('px-3 py-2.5', NUMERICOS.includes(tipoDe(c, f)) && 'text-right whitespace-nowrap')}>
                        <Valor valor={f[c.clave]} tipo={tipoDe(c, f)} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
              {totales && (
                <tfoot>
                  <tr className="font-semibold">
                    {columnas.map((c, i) => (
                      <td key={c.clave} className={unir('px-3 pt-3', NUMERICOS.includes(c.tipo) && 'text-right whitespace-nowrap')}>
                        {c.clave in totales ? <Valor valor={totales[c.clave]} tipo={c.tipo} /> : i === 0 ? 'Total' : ''}
                      </td>
                    ))}
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
          <ul className="flex flex-col gap-3 sm:hidden">
            {filas.map((f, i) => (
              <li key={i} className="rounded-2xl border border-linea px-4 py-3">
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                  {columnas.map((c) => (
                    <div key={c.clave} className="contents">
                      <dt className="text-sm text-cafe-suave">{c.titulo}</dt>
                      <dd className="text-right">
                        <Valor valor={f[c.clave]} tipo={tipoDe(c, f)} />
                      </dd>
                    </div>
                  ))}
                </dl>
              </li>
            ))}
            {totales && (
              <li className="rounded-2xl bg-pista px-4 py-3 font-semibold">
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                  <dt>Total</dt>
                  <dd />
                  {columnas
                    .filter((c) => c.clave in totales)
                    .map((c) => (
                      <div key={c.clave} className="contents">
                        <dt className="text-sm font-normal text-cafe-suave">{c.titulo}</dt>
                        <dd className="text-right">
                          <Valor valor={totales[c.clave]} tipo={c.tipo} />
                        </dd>
                      </div>
                    ))}
                </dl>
              </li>
            )}
          </ul>
        </>
      )}
    </Tarjeta>
  )
}
