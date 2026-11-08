"""Configuración del servicio HTTP, desde variables de entorno."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cuysearch.motores.base import USER_AGENT


class Settings(BaseSettings):
    """Configuración centralizada y validada desde variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Si hay SearXNG propio, se prueba primero; si no, se usan los motores gratuitos.
    searxng_base_url: str | None = None
    # "auto" o una lista separada por comas (ver cuysearch.motores.TODOS).
    cuysearch_motores: str = "auto"
    cuysearch_api_key: str | None = None
    cuysearch_host: str = "127.0.0.1"
    cuysearch_port: int = Field(default=8090, ge=1, le=65_535)
    cuysearch_log_level: str = "info"

    cuysearch_request_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    cuysearch_extract_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    cuysearch_max_fetch_bytes: int = Field(default=1_000_000, ge=1_024, le=20_000_000)
    cuysearch_max_content_chars: int = Field(default=8_000, ge=100, le=200_000)
    cuysearch_max_redirects: int = Field(default=3, ge=0, le=10)
    cuysearch_cache_ttl_seconds: int = Field(default=300, ge=0, le=86_400)
    cuysearch_cache_max_entries: int = Field(default=32, ge=0, le=10_000)
    cuysearch_cache_max_bytes: int = Field(default=1_000_000, ge=0, le=100_000_000)
    cuysearch_max_concurrent_extractions: int = Field(default=2, ge=1, le=20)
    cuysearch_http_keepalive_connections: int = Field(default=1, ge=0, le=20)
    cuysearch_user_agent: str = USER_AGENT
    cuysearch_cors_origins: str = ""

    @property
    def motores(self) -> list[str] | str:
        valor = self.cuysearch_motores.strip()
        if not valor or valor == "auto":
            return "auto"
        return [m.strip() for m in valor.split(",") if m.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cuysearch_cors_origins.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
