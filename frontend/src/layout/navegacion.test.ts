import { seccionesVisibles } from './navegacion'

const nombres = (permisos: string[]) => seccionesVisibles(permisos).map((s) => s.nombre)

describe('secciones visibles por permisos', () => {
  it('el cajero ve vender, caja, encargos y gastos, sin inicio ni inventario', () => {
    expect(
      nombres([
        'ventas.crear',
        'caja.abrir',
        'caja.cerrar',
        'encargos.crear',
        'gastos.crear_caja',
        'reportes.ver_caja_propia',
      ]),
    ).toEqual(['Vender', 'Caja', 'Encargos', 'Gastos', 'Reportes'])
  })
  it('producción ve inventario y compras', () => {
    expect(nombres(['inventario.ver', 'compras.crear'])).toEqual(['Inventario', 'Compras'])
  })
  it('sin permisos no ve nada', () => {
    expect(nombres([])).toEqual([])
  })
})
