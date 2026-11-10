"""Soportes y fotos: imágenes y PDF de máximo 5 MB, con nombre aleatorio (sección 11)."""

import re
import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import obtener_config
from app.shared.errores import ErrorNegocio, NoEncontrado

# El tipo se decide por los primeros bytes del archivo, no por la extensión ni el
# Content-Type que manda el navegador.
FIRMAS: list[tuple[str, str, bytes, int]] = [
    ("image/jpeg", "jpg", b"\xff\xd8\xff", 0),
    ("image/png", "png", b"\x89PNG\r\n\x1a\n", 0),
    ("image/webp", "webp", b"WEBP", 8),
    ("application/pdf", "pdf", b"%PDF-", 0),
]
TIPOS_POR_EXTENSION = {ext: tipo for tipo, ext, _, _ in FIRMAS}
NOMBRE_VALIDO = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp|pdf)$")


def detectar_tipo(contenido: bytes) -> tuple[str, str]:
    for tipo, extension, firma, desde in FIRMAS:
        if contenido[desde : desde + len(firma)] == firma:
            if tipo == "image/webp" and contenido[:4] != b"RIFF":
                continue
            return tipo, extension
    raise ErrorNegocio(
        "TIPO_ARCHIVO_NO_PERMITIDO", "Solo se aceptan imágenes (JPG, PNG, WebP) y PDF.", status=415
    )


class Almacen(Protocol):
    def guardar(self, nombre: str, contenido: bytes) -> None: ...
    def leer(self, nombre: str) -> bytes: ...


class AlmacenLocal:
    """Guarda en una carpeta (volumen de Docker). En servidor se puede cambiar por S3 u otro
    almacenamiento implementando el mismo protocolo."""

    def __init__(self, carpeta: str) -> None:
        self.carpeta = Path(carpeta)

    def guardar(self, nombre: str, contenido: bytes) -> None:
        self.carpeta.mkdir(parents=True, exist_ok=True)
        (self.carpeta / nombre).write_bytes(contenido)

    def leer(self, nombre: str) -> bytes:
        ruta = self.carpeta / nombre
        if not ruta.is_file():
            raise NoEncontrado("el archivo", nombre)
        return ruta.read_bytes()


def almacen() -> Almacen:
    return AlmacenLocal(obtener_config().archivos_dir)


def guardar(contenido: bytes, destino: Almacen) -> str:
    if len(contenido) > obtener_config().archivos_max_bytes:
        raise ErrorNegocio("ARCHIVO_MUY_GRANDE", "El archivo supera el máximo de 5 MB.", status=413)
    if not contenido:
        raise ErrorNegocio("ARCHIVO_VACIO", "El archivo está vacío.", status=422)
    _, extension = detectar_tipo(contenido)
    nombre = f"{uuid.uuid4().hex}.{extension}"
    destino.guardar(nombre, contenido)
    return nombre


def leer(nombre: str, origen: Almacen) -> tuple[bytes, str]:
    if not NOMBRE_VALIDO.match(nombre):
        raise NoEncontrado("el archivo", nombre)
    return origen.leer(nombre), TIPOS_POR_EXTENSION[nombre.rsplit(".", 1)[1]]
