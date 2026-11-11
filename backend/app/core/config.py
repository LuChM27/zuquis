"""Configuración de la aplicación. Todo cambia por variables de entorno (RNF-04)."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores que alguna vez estuvieron escritos en el repositorio: son públicos.
SECRETOS_PUBLICOS = {
    "solo-para-desarrollo-no-usar-en-produccion",
    "cambiar-por-una-clave-larga-y-aleatoria",
}
GENERAR_SECRETO = 'python -c "import secrets; print(secrets.token_urlsafe(48))"'


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://zuquis:zuquis@localhost:5432/zuquis"
    # Obligatorio y sin valor por defecto: con una clave conocida cualquiera puede firmar
    # tokens de administrador.
    jwt_secret: str
    jwt_algoritmo: str = "HS256"
    access_minutos: int = 15
    refresh_dias: int = 7
    cookie_secure: bool = True

    login_max_intentos: int = 5
    login_bloqueo_minutos: int = 15
    login_limite_por_minuto: int = 20

    zona_horaria: str = "America/Bogota"
    cors_origins: str = "http://localhost:5173"
    archivos_dir: str = "./archivos"
    archivos_max_bytes: int = 5 * 1024 * 1024

    @field_validator("jwt_secret")
    @classmethod
    def _secreto_seguro(cls, v: str) -> str:
        if v in SECRETOS_PUBLICOS or len(v) < 32:
            raise ValueError(
                "JWT_SECRET debe ser una clave aleatoria de al menos 32 caracteres que no "
                f"esté en el repositorio. Genera una con: {GENERAR_SECRETO}"
            )
        return v

    @property
    def cors_lista(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def obtener_config() -> Configuracion:
    return Configuracion()
