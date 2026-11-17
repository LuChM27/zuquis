"""Exportación a Excel y PDF y reporte PUC (#47)."""

from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from app.shared.pdf import pdf_disponible
from tests.fixtures_reportes import reporte, seccion, vendida
from tests.fixtures_ventas import API, post, venta_mockup

HOY = date(2026, 11, 10)


def _abrir(cliente, admin, reloj):
    reloj("2026-11-10T09:00:00-05:00")
    r = cliente.post(f"{API}/caja/abrir", headers=admin, json={"base_inicial": 100000})
    assert r.status_code == 201, r.text


def test_suma_del_excel_igual_al_json(cliente, admin, carta, metodos, reloj):
    _abrir(cliente, admin, reloj)
    vendida(cliente, admin, venta_mockup(carta, metodos))
    json_ = reporte(cliente, admin, "ventas", HOY, HOY).json()
    r = reporte(cliente, admin, "ventas", HOY, HOY, formato="xlsx")
    assert r.status_code == 200, r.text
    assert r.headers["content-disposition"].endswith('zuquis-ventas-2026-11-10-2026-11-10.xlsx"')
    hoja = load_workbook(BytesIO(r.content))["Por método de pago"]
    assert hoja["A1"].value.endswith("· Ventas")
    filas = [row for row in hoja.iter_rows(min_row=7, values_only=True) if row[0] != "Total"]
    assert (
        sum(f[2] for f in filas if f[0])
        == seccion(json_, "Por método de pago")["totales"]["ventas"]
    )
    total = [row for row in hoja.iter_rows(min_row=7) if row[0].value == "Total"][0]
    assert str(total[2].value).startswith("=SUM(")
    assert hoja.cell(row=7, column=3).number_format == '"$"#,##0'


def test_excel_sin_permiso_exportar_403(cliente, crear_usuario, login):
    contador = login(crear_usuario("contador", email="conta@zuquis.co"))
    assert reporte(cliente, contador, "gastos", HOY, HOY, formato="xlsx").status_code == 200
    produccion = login(crear_usuario("produccion", email="prod@zuquis.co"))
    r = reporte(cliente, produccion, "mermas", HOY, HOY, formato="xlsx")
    assert r.status_code == 403


def test_pdf_responde_pdf(cliente, admin, carta, metodos, reloj):
    _abrir(cliente, admin, reloj)
    vendida(cliente, admin, venta_mockup(carta, metodos))
    r = reporte(cliente, admin, "ventas", HOY, HOY, formato="pdf")
    if not pdf_disponible():
        assert r.status_code == 503
        return
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_puc_precargado_en_categorias_y_metodos(cliente, admin):
    cats = {
        c["nombre"]: c["cuenta_puc"]
        for c in cliente.get(f"{API}/categorias-gasto", headers=admin).json()
    }
    metodos = {
        m["nombre"]: m["cuenta_puc"]
        for m in cliente.get(f"{API}/metodos-pago", headers=admin).json()
    }
    assert (cats["Arriendo del local"], metodos["Efectivo"]) == ("5120", "1105")


def test_reporte_puc_por_cuenta(cliente, admin, carta, metodos, reloj):
    _abrir(cliente, admin, reloj)
    # 2 croissants a $7.500 (costo PEPS $2.000 c/u) + propina $1.000, todo en efectivo.
    vendida(
        cliente,
        admin,
        {
            "tipo_servicio": "local",
            "items": [{"producto_id": carta["croissant"]["id"], "cantidad": "2"}],
            "propina": 1000,
            "pagos": [{"metodo_pago_id": metodos["Efectivo"], "monto": 16000}],
        },
    )
    r = reporte(cliente, admin, "puc", HOY, HOY)
    assert r.status_code == 200, r.text
    cuentas = {f["cuenta"]: f["monto"] for f in seccion(r.json(), "Por cuenta")["filas"]}
    assert cuentas == {"4120": 15000, "6120": 4000, "2380": 1000, "1105": 16000}


def test_puc_sin_codigo_visible(cliente, admin, carta, reloj):
    _abrir(cliente, admin, reloj)
    sin = post(cliente, admin, "/metodos-pago", {"nombre": "Daviplata"})
    vendida(
        cliente,
        admin,
        {
            "tipo_servicio": "local",
            "items": [{"producto_id": carta["pastel"]["id"], "cantidad": "1"}],
            "pagos": [{"metodo_pago_id": sin["id"], "monto": 4500}],
        },
    )
    cuentas = {
        f["cuenta"]: f["monto"]
        for f in seccion(reporte(cliente, admin, "puc", HOY, HOY).json(), "Por cuenta")["filas"]
    }
    assert cuentas["Sin código"] == 4500


def test_texto_que_parece_formula_no_se_ejecuta_en_excel():
    """Un nombre como "=HYPERLINK(...)" escrito por un usuario sale como texto, no fórmula."""
    from datetime import datetime

    from app.modules.reportes.esquemas import Reporte, col
    from app.modules.reportes.esquemas import seccion as nueva
    from app.modules.reportes.exportar import a_xlsx

    r = Reporte(
        tipo="ventas",
        titulo="Ventas",
        sede="Centro",
        desde=HOY,
        hasta=HOY,
        generado_en=datetime(2026, 11, 10, 20, 0),
        secciones=[
            nueva(
                "Por producto",
                [col("nombre", "Producto"), col("ventas", "Ventas", "pesos")],
                [{"nombre": '=HYPERLINK("http://x","y")', "ventas": 1000}],
            )
        ],
    )
    hoja = load_workbook(BytesIO(a_xlsx(r, "Zuqui's")))["Por producto"]
    celda = hoja.cell(row=7, column=1)
    assert celda.data_type == "s"
    assert celda.value == '=HYPERLINK("http://x","y")'


def test_hojas_con_titulos_largos_o_repetidos():
    from datetime import datetime

    from app.modules.reportes.esquemas import Reporte, col
    from app.modules.reportes.esquemas import seccion as nueva
    from app.modules.reportes.exportar import a_xlsx

    largo = "Una sección con un título bastante largo que pasa de 31"
    secciones = [nueva(t, [col("a", "A")], [{"a": "x"}]) for t in (largo, largo, "[]:*?/\\")]
    r = Reporte(
        tipo="ventas", titulo="Ventas", sede="Centro", desde=HOY, hasta=HOY,
        generado_en=datetime(2026, 11, 10, 20, 0), secciones=secciones,
    )  # fmt: skip
    nombres = load_workbook(BytesIO(a_xlsx(r, "Zuqui's"))).sheetnames
    assert len(nombres) == 3 and len(set(nombres)) == 3
    assert all(0 < len(n) <= 31 for n in nombres)
