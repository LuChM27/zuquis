"""Límite de peticiones en memoria (ventana deslizante por IP).

Suficiente para un solo proceso de API, que es el despliegue del local y del servidor
inicial. Si se escala a varios procesos hay que moverlo a PostgreSQL o Redis.
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request

from app.shared.errores import ErrorNegocio

_lock = threading.Lock()
_registros: dict[str, deque[float]] = defaultdict(deque)


def limitar(
    nombre: str, maximo: Callable[[], int], ventana_s: int = 60
) -> Callable[[Request], None]:
    def dependencia(request: Request) -> None:
        clave = f"{nombre}:{request.client.host if request.client else '?'}"
        ahora = time.monotonic()
        with _lock:
            marcas = _registros[clave]
            while marcas and ahora - marcas[0] > ventana_s:
                marcas.popleft()
            if len(marcas) >= maximo():
                raise ErrorNegocio(
                    "DEMASIADAS_PETICIONES",
                    "Demasiados intentos. Espera un minuto e intenta de nuevo.",
                    status=429,
                )
            marcas.append(ahora)

    return dependencia


def reiniciar() -> None:
    """Solo para pruebas."""
    with _lock:
        _registros.clear()
