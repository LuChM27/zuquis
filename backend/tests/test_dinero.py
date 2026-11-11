from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from app.shared.dinero import (
    Cantidad,
    CostoUnitario,
    DineroInvalido,
    Pesos,
    Porcentaje,
    aplicar_porcentaje,
    costo_linea,
    dividir_costo,
    redondear_a_peso,
    sumar_pesos,
)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("0.5", 1),
        ("1.5", 2),
        ("2.4999", 2),
        ("12499.5", 12500),
        ("-0.5", -1),
        ("-1.4", -1),
        ("0", 0),
    ],
)
def test_redondeo_half_up(valor, esperado):
    assert redondear_a_peso(Decimal(valor)) == esperado


def test_redondeo_rechaza_float():
    with pytest.raises(DineroInvalido):
        redondear_a_peso(0.5)


def test_costo_linea_redondea_una_sola_vez():
    # 250 g de harina a $3,000000/g = $750
    assert costo_linea(Decimal("250"), Decimal("3.000000")) == 750
    # 0,3333 × 4,500000 = 1,49985 → 1
    assert costo_linea(Decimal("0.3333"), Decimal("4.5")) == 1
    # 3 × 0,5 = 1,5 → 2 (no 1 + 1 + 1 por separado)
    assert costo_linea(Decimal("3"), Decimal("0.5")) == 2


def test_costo_linea_negativo_para_reversos():
    assert costo_linea(Decimal("-3"), Decimal("0.5")) == -2


@pytest.mark.parametrize(
    ("monto", "pct", "esperado"),
    [
        (12500, "10", 1250),
        (9000, "33.3333", 3000),  # 2999,997 → 3000
        (49500, "6.0606", 3000),  # 2999,997 → 3000
        (1999, "50", 1000),  # 999,5 → 1000
        (12500, "100", 12500),  # cortesía
        (12500, "0", 0),
    ],
)
def test_aplicar_porcentaje(monto, pct, esperado):
    assert aplicar_porcentaje(monto, Decimal(pct)) == esperado


def test_aplicar_porcentaje_exige_pesos_enteros():
    with pytest.raises(DineroInvalido):
        aplicar_porcentaje(12500.0, Decimal("10"))


def test_dividir_costo_produccion():
    # 12 pasteles que costaron $10.000 → $833,333333 cada uno
    assert dividir_costo(10000, Decimal("12")) == Decimal("833.333333")
    with pytest.raises(DineroInvalido):
        dividir_costo(10000, Decimal("0"))


def test_suma_de_lineas_redondeadas_cuadra_con_el_total():
    lineas = [costo_linea(Decimal("1"), Decimal("0.5")) for _ in range(3)]  # 1, 1, 1
    assert sumar_pesos(lineas) == 3
    with pytest.raises(DineroInvalido):
        sumar_pesos([1, 2.0])


class Linea(BaseModel):
    precio: Pesos
    cantidad: Cantidad
    costo: CostoUnitario
    descuento: Porcentaje


def test_api_acepta_decimales_como_texto():
    linea = Linea(precio=12500, cantidad="0.1", costo="4.2", descuento="10")
    assert linea.cantidad == Decimal("0.1000")
    assert linea.costo == Decimal("4.200000")


def test_api_rechaza_float():
    with pytest.raises(ValidationError):
        Linea(precio=12500, cantidad=0.1, costo="4.2", descuento="10")
    with pytest.raises(ValidationError):
        Linea(precio=12500.0, cantidad="1", costo="4.2", descuento="10")
    with pytest.raises(ValidationError):
        Linea.model_validate_json(
            '{"precio": 12500, "cantidad": 0.1, "costo": "1", "descuento": "0"}'
        )


def test_api_rechaza_mas_decimales_de_los_permitidos():
    with pytest.raises(ValidationError):
        Linea(precio=1, cantidad="0.00001", costo="1", descuento="0")


def test_api_serializa_decimales_como_texto():
    linea = Linea(precio=12500, cantidad="2.5", costo="4.2", descuento="10")
    assert linea.model_dump(mode="json") == {
        "precio": 12500,
        "cantidad": "2.5000",
        "costo": "4.200000",
        "descuento": "10.0000",
    }
