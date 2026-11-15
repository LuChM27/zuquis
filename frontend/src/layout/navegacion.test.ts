import { seccionesVisibles } from './navegacion'

const nombres = (permisos: string[]) => seccionesVisibles(permisos).map((s) => s.nombre)

describe('secciones visibles por permisos', () => {
  it('el cajero ve vender, sus ventas, caja, encargos y gastos, sin inicio ni inventario', () => {
    expect(
      nombres([
        'ventas.crear',
        'caja.abrir',
        'caja.cerrar',
        'encargos.crear',
        'gastos.crear_caja',
        'reportes.ver_caja_propia',
      ]),
    ).toEqual(['Vender', 'Ventas', 'Caja', 'Encargos', 'Gastos', 'Reportes'])
  })
  it('producción ve inventario, carta (por las recetas) y compras', () => {
    expect(nombres(['inventario.ver', 'compras.crear', 'recetas.editar'])).toEqual(['Inventario', 'Carta', 'Compras'])
  })
  it('con solo producción ve Compras, donde se registra la producción', () => {
    expect(nombres(['produccion.crear'])).toEqual(['Compras'])
  })
  it('sin permisos no ve nada', () => {
    expect(nombres([])).toEqual([])
  })
})
