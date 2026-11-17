"""Formato único de errores: {"codigo": "...", "mensaje": "...", "detalle": {...}}."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorNegocio(Exception):
    """Error de dominio con código estable para el frontend."""

    status = 400

    def __init__(
        self,
        codigo: str,
        mensaje: str,
        detalle: dict[str, Any] | None = None,
        status: int | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalle = detalle or {}
        if status is not None:
            self.status = status


class NoEncontrado(ErrorNegocio):
    status = 404

    def __init__(self, entidad: str, id_: Any = None) -> None:
        super().__init__(
            "NO_ENCONTRADO",
            f"No se encontró {entidad}.",
            {"entidad": entidad, "id": str(id_) if id_ else None},
        )


class Conflicto(ErrorNegocio):
    status = 409


class NoAutenticado(ErrorNegocio):
    status = 401

    def __init__(
        self, mensaje: str = "Debes iniciar sesión.", codigo: str = "NO_AUTENTICADO"
    ) -> None:
        super().__init__(codigo, mensaje)


class SinPermiso(ErrorNegocio):
    status = 403

    def __init__(self, permiso: str | None = None) -> None:
        super().__init__(
            "SIN_PERMISO",
            "No tienes permiso para hacer esta operación.",
            {"permiso": permiso} if permiso else None,
        )


def _respuesta(
    status: int, codigo: str, mensaje: str, detalle: Any = None, headers=None
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"codigo": codigo, "mensaje": mensaje, "detalle": detalle or {}},
        headers=headers,
    )


_CODIGOS_HTTP = {
    401: ("NO_AUTENTICADO", "Debes iniciar sesión."),
    403: ("SIN_PERMISO", "No tienes permiso para hacer esta operación."),
    404: ("NO_ENCONTRADO", "El recurso no existe."),
    405: ("METODO_NO_PERMITIDO", "Método no permitido."),
    413: ("ARCHIVO_MUY_GRANDE", "El archivo supera el tamaño permitido."),
    429: ("DEMASIADAS_PETICIONES", "Demasiados intentos. Espera un momento."),
}


def _mensaje(error: dict) -> str:
    """Pydantic antepone "Value error, " a los mensajes de las reglas propias; se quita."""
    texto = str(error["msg"])
    return texto.removeprefix("Value error, ") if error["type"] == "value_error" else texto


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorNegocio)
    async def _negocio(_: Request, exc: ErrorNegocio) -> JSONResponse:
        return _respuesta(exc.status, exc.codigo, exc.mensaje, exc.detalle)

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, exc: RequestValidationError) -> JSONResponse:
        errores = [
            {"campo": ".".join(str(p) for p in e["loc"][1:]), "mensaje": _mensaje(e)}
            for e in exc.errors()
        ]
        # Si una regla del negocio explica el error, ese es el mensaje principal.
        propios = [_mensaje(e) for e in exc.errors() if e["type"] == "value_error"]
        mensaje = propios[0] if propios else "Hay datos inválidos en la petición."
        return _respuesta(422, "VALIDACION", mensaje, {"errores": errores})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        codigo, mensaje = _CODIGOS_HTTP.get(exc.status_code, ("ERROR_HTTP", str(exc.detail)))
        return _respuesta(exc.status_code, codigo, mensaje, headers=getattr(exc, "headers", None))
