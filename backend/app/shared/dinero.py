"""Dinero y cantidades exactas (RNF-01, sección 6 de la especificación).

- Montos en pesos: ``int`` (BIGINT). Sin centavos: $12.500 se guarda como 12500.
- Costos unitarios: ``Decimal`` con 6 decimales (NUMERIC(18,6)).
- Cantidades de inventario: ``Decimal`` con 4 decimales (NUMERIC(18,4)).
- Porcentajes: ``Decimal`` con 4 decimales (NUMERIC(7,4)); 10 % se escribe "10".
- Los decimales viajan como string en JSON. Nunca se acepta ni se produce un float.
- El costo de una línea se redondea a peso una sola vez, con ROUND_HALF_UP.
"""

from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from typing import Annotated, Any

from pydantic import BeforeValidator, Field, PlainSerializer, StrictInt
from sqlalchemy import BigInteger, Numeric

# Precisión holgada para operaciones intermedias; el redondeo de negocio es explícito.
CONTEXTO = Context(prec=38, rounding=ROUND_HALF_UP)

ESCALA_COSTO = Decimal("0.000001")
ESCALA_CANTIDAD = Decimal("0.0001")
ESCALA_PORCENTAJE = Decimal("0.0001")
CIEN = Decimal(100)


class DineroInvalido(ValueError):
    pass


def a_decimal(valor: Any) -> Decimal:
    """Convierte str/int/Decimal a Decimal. Rechaza float y bool."""
    if isinstance(valor, (bool, float)):
        raise DineroInvalido(
            "Los decimales deben enviarse como texto, no como número con decimales."
        )
    if isinstance(valor, Decimal):
        resultado = valor
    elif isinstance(valor, int):
        resultado = Decimal(valor)
    elif isinstance(valor, str):
        texto = valor.strip()
        try:
            resultado = Decimal(texto)
        except Exception as exc:
            raise DineroInvalido(f"'{valor}' no es un número válido.") from exc
    else:
        raise DineroInvalido(f"Tipo no soportado: {type(valor).__name__}.")
    if not resultado.is_finite():
        raise DineroInvalido("El número debe ser finito.")
    return resultado


def redondear_a_peso(valor: Decimal) -> int:
    """Redondea a peso entero con ROUND_HALF_UP (0,5 sube; -0,5 baja a -1)."""
    if isinstance(valor, float):
        raise DineroInvalido("No se aceptan float.")
    return int(Decimal(valor).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def costo_linea(cantidad: Decimal, costo_unitario: Decimal) -> int:
    """Costo de una línea: cantidad × costo unitario en Decimal, redondeado una sola vez."""
    with localcontext(CONTEXTO):
        return redondear_a_peso(a_decimal(cantidad) * a_decimal(costo_unitario))


def aplicar_porcentaje(monto: int, porcentaje: Decimal) -> int:
    """Valor del porcentaje sobre un monto en pesos, redondeado a peso. 10 % de 12500 → 1250."""
    if not isinstance(monto, int) or isinstance(monto, bool):
        raise DineroInvalido("El monto debe ser un entero en pesos.")
    with localcontext(CONTEXTO):
        return redondear_a_peso(Decimal(monto) * a_decimal(porcentaje) / CIEN)


def dividir_costo(costo_total: Decimal | int, unidades: Decimal) -> Decimal:
    """Costo unitario = costo total / unidades, con 6 decimales (p. ej. lote de producción)."""
    with localcontext(CONTEXTO):
        unidades_dec = a_decimal(unidades)
        if unidades_dec <= 0:
            raise DineroInvalido("Las unidades deben ser mayores que cero.")
        return (a_decimal(costo_total) / unidades_dec).quantize(ESCALA_COSTO)


def sumar_pesos(montos: list[int]) -> int:
    """Total = suma de líneas ya redondeadas, para que siempre cuadre con el detalle."""
    for m in montos:
        if not isinstance(m, int) or isinstance(m, bool):
            raise DineroInvalido("Solo se suman montos enteros en pesos.")
    return sum(montos)


# --- Tipos para Pydantic -------------------------------------------------------------------


def _validador_decimal(escala: Decimal):
    def validar(valor: Any) -> Decimal:
        if isinstance(valor, (int, Decimal)) and not isinstance(valor, bool):
            # Un entero de JSON es exacto; se acepta. Los float nunca.
            valor = Decimal(valor)
        elif not isinstance(valor, str):
            raise DineroInvalido('Los decimales deben enviarse como texto, por ejemplo "2.5".')
        dec = a_decimal(valor)
        if dec != dec.quantize(escala):
            raise DineroInvalido(f"Máximo {abs(escala.as_tuple().exponent)} decimales.")
        return dec.quantize(escala)

    return validar


def _serializador(escala: Decimal):
    return PlainSerializer(
        lambda d: str(Decimal(d).quantize(escala)), return_type=str, when_used="json"
    )


Pesos = Annotated[StrictInt, Field(description="Monto en pesos, entero sin centavos")]
"""Monto en pesos. En JSON es un número entero."""

CostoUnitario = Annotated[
    Decimal,
    BeforeValidator(_validador_decimal(ESCALA_COSTO)),
    Field(max_digits=18, decimal_places=6),
    _serializador(ESCALA_COSTO),
]
Cantidad = Annotated[
    Decimal,
    BeforeValidator(_validador_decimal(ESCALA_CANTIDAD)),
    Field(max_digits=18, decimal_places=4),
    _serializador(ESCALA_CANTIDAD),
]
Porcentaje = Annotated[
    Decimal,
    BeforeValidator(_validador_decimal(ESCALA_PORCENTAJE)),
    Field(max_digits=7, decimal_places=4),
    _serializador(ESCALA_PORCENTAJE),
]


# --- Tipos de columna para SQLAlchemy -------------------------------------------------------


def MontoPesos() -> BigInteger:  # noqa: N802 - se usa como un tipo
    return BigInteger()


def NumericCosto() -> Numeric:  # noqa: N802
    return Numeric(18, 6, asdecimal=True)


def NumericCantidad() -> Numeric:  # noqa: N802
    return Numeric(18, 4, asdecimal=True)


def NumericPorcentaje() -> Numeric:  # noqa: N802
    return Numeric(7, 4, asdecimal=True)
