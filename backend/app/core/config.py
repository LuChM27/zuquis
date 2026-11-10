"""Configuración de la aplicación. Todo cambia por variables de entorno (RNF-04)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://zuquis:zuquis@localhost:5432/zuquis"
    jwt_secret: str = "solo-para-desarrollo-no-usar-en-produccion"  # noqa: S105
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

    @property
    def cors_lista(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def obtener_config() -> Configuracion:
    return Configuracion()
