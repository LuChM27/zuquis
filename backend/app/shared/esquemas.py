"""Utilidades para esquemas de entrada."""

from typing import Any, ClassVar

from pydantic import BaseModel, model_validator


class EdicionParcial(BaseModel):
    """Base de los esquemas PATCH: un campo omitido no cambia, pero un ``null`` explícito en un
    campo obligatorio se rechaza (no puede llegar a una columna NOT NULL).

    Las subclases declaran en ``NO_NULOS`` los campos que no se pueden dejar vacíos.
    """

    NO_NULOS: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="before")
    @classmethod
    def _sin_nulos_obligatorios(cls, datos: Any) -> Any:
        if isinstance(datos, dict):
            nulos = [c for c in cls.NO_NULOS if c in datos and datos[c] is None]
            if nulos:
                raise ValueError(f"Estos campos no pueden quedar vacíos: {', '.join(nulos)}.")
        return datos
