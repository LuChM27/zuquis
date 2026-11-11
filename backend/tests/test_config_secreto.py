import pytest
from pydantic import ValidationError

from app.core.config import Configuracion


@pytest.mark.parametrize(
    "secreto",
    [
        "solo-para-desarrollo-no-usar-en-produccion",
        "cambiar-por-una-clave-larga-y-aleatoria",
        "corta",
    ],
)
def test_jwt_secret_publico_o_corto_impide_arrancar(secreto):
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Configuracion(jwt_secret=secreto, _env_file=None)


def test_jwt_secret_es_obligatorio(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Configuracion(_env_file=None)


def test_jwt_secret_aleatorio_se_acepta():
    assert Configuracion(jwt_secret="x" * 16 + "aleatorio-de-prueba-32", _env_file=None).jwt_secret
