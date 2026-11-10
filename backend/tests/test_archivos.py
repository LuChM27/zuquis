PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
PDF = b"%PDF-1.7\n" + b"0" * 100


def test_subir_y_descargar_imagen(cliente, admin):
    r = cliente.post(
        "/api/v1/archivos", headers=admin, files={"archivo": ("soporte.png", PNG, "image/png")}
    )
    assert r.status_code == 201
    nombre = r.json()["nombre"]
    assert nombre.endswith(".png") and "soporte" not in nombre
    r = cliente.get(r.json()["url"], headers=admin)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == PNG


def test_pdf_permitido(cliente, admin):
    r = cliente.post(
        "/api/v1/archivos",
        headers=admin,
        files={"archivo": ("factura.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 201


def test_ejecutable_renombrado_es_rechazado(cliente, admin):
    exe = b"MZ\x90\x00" + b"\x00" * 100
    r = cliente.post(
        "/api/v1/archivos", headers=admin, files={"archivo": ("foto.jpg", exe, "image/jpeg")}
    )
    assert r.status_code == 415
    assert r.json()["codigo"] == "TIPO_ARCHIVO_NO_PERMITIDO"


def test_archivo_de_6_mb_es_rechazado(cliente, admin):
    grande = PNG + b"\x00" * (6 * 1024 * 1024)
    r = cliente.post(
        "/api/v1/archivos", headers=admin, files={"archivo": ("grande.png", grande, "image/png")}
    )
    assert r.status_code == 413
    assert r.json()["codigo"] == "ARCHIVO_MUY_GRANDE"


def test_nombre_con_ruta_no_permite_salir_de_la_carpeta(cliente, admin):
    assert cliente.get("/api/v1/archivos/..%2F..%2Fsecreto.png", headers=admin).status_code == 404
