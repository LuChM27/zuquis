from fastapi import APIRouter, Depends, File, Response, UploadFile
from pydantic import BaseModel

from app.core.config import obtener_config
from app.core.deps import Contexto, obtener_contexto
from app.modules.archivos import service

router = APIRouter(prefix="/archivos", tags=["Archivos"])


class ArchivoSalida(BaseModel):
    nombre: str
    url: str


@router.post("", response_model=ArchivoSalida, status_code=201)
async def subir(
    archivo: UploadFile = File(...),
    _: Contexto = Depends(obtener_contexto),
    almacen: service.Almacen = Depends(service.almacen),
) -> ArchivoSalida:
    # Se lee un byte de más para detectar archivos que superan el límite sin cargarlos enteros.
    contenido = await archivo.read(obtener_config().archivos_max_bytes + 1)
    nombre = service.guardar(contenido, almacen)
    return ArchivoSalida(nombre=nombre, url=f"/api/v1/archivos/{nombre}")


@router.get("/{nombre}")
def descargar(
    nombre: str,
    _: Contexto = Depends(obtener_contexto),
    almacen: service.Almacen = Depends(service.almacen),
) -> Response:
    contenido, tipo = service.leer(nombre, almacen)
    return Response(
        content=contenido,
        media_type=tipo,
        headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )
