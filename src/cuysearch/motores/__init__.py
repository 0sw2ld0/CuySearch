"""Motores de búsqueda disponibles y cómo se eligen.

Sin configurar nada se usan los motores gratuitos, en este orden, desde la
conexión de quien llama: DuckDuckGo, Bing, Brave, Mojeek y Wikipedia. SearXNG
y los servicios con clave sólo entran si el usuario da su URL o su clave.
Google no está: sus condiciones no permiten consultarlo así.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from cuysearch.motores.apis import BraveAPI, Exa, Ollama, SearXNG, Tavily
from cuysearch.motores.base import ErrorDeMotor, Motor, MotorBloqueado
from cuysearch.motores.bing import Bing
from cuysearch.motores.brave import Brave
from cuysearch.motores.duckduckgo import DuckDuckGo
from cuysearch.motores.mojeek import Mojeek
from cuysearch.motores.wikipedia import Wikipedia

GRATUITOS = ("duckduckgo", "bing", "brave", "mojeek", "wikipedia")
CON_CLAVE = ("ollama", "brave_api", "tavily", "exa")
TODOS = GRATUITOS + ("searxng",) + CON_CLAVE

# Variables de entorno de cada clave. OLLAMA_API_KEY no activa Ollama en el
# modo automático, porque muchos la tienen para otra cosa: hay que pedirlo.
VARIABLES_DE_CLAVE = {
    "ollama": "OLLAMA_API_KEY",
    "brave_api": "BRAVE_API_KEY",
    "tavily": "TAVILY_API_KEY",
    "exa": "EXA_API_KEY",
}
_AUTOMATICOS_CON_CLAVE = ("brave_api", "tavily", "exa")

__all__ = [
    "CON_CLAVE", "GRATUITOS", "TODOS", "Configuracion", "ErrorDeMotor", "Motor", "MotorBloqueado",
    "crear", "orden_automatico",
]


@dataclass(frozen=True)
class Configuracion:
    searxng_url: str | None = None
    claves: Mapping[str, str] = field(default_factory=dict)
    tiempo: float = 10.0

    @classmethod
    def desde_entorno(cls, entorno: Mapping[str, str] | None = None) -> Configuracion:
        entorno = os.environ if entorno is None else entorno
        claves = {m: entorno[v].strip() for m, v in VARIABLES_DE_CLAVE.items() if (entorno.get(v) or "").strip()}
        return cls(searxng_url=(entorno.get("CUYSEARCH_SEARXNG_URL") or "").strip() or None, claves=claves)


def orden_automatico(config: Configuracion) -> list[str]:
    orden = ["searxng"] if config.searxng_url else []
    orden += [m for m in _AUTOMATICOS_CON_CLAVE if config.claves.get(m)]
    return orden + list(GRATUITOS)


def crear(nombre: str, config: Configuracion) -> Motor:
    """Crea un motor; ValueError si no existe o le falta su URL o su clave."""
    tiempo = config.tiempo
    if nombre == "duckduckgo":
        return DuckDuckGo(tiempo)
    if nombre == "bing":
        return Bing(tiempo)
    if nombre == "brave":
        return Brave(tiempo)
    if nombre == "mojeek":
        return Mojeek(tiempo)
    if nombre == "wikipedia":
        return Wikipedia(tiempo)
    if nombre == "searxng":
        if not config.searxng_url:
            raise ValueError("searxng necesita una URL (CUYSEARCH_SEARXNG_URL)")
        return SearXNG(config.searxng_url, max(tiempo, 15.0))
    clases = {"ollama": Ollama, "brave_api": BraveAPI, "tavily": Tavily, "exa": Exa}
    if nombre in clases:
        clave = config.claves.get(nombre)
        if not clave:
            raise ValueError(f"{nombre} necesita su clave ({VARIABLES_DE_CLAVE[nombre]})")
        return clases[nombre](clave, max(tiempo, 15.0))
    raise ValueError(f"Motor desconocido: {nombre}. Disponibles: {', '.join(TODOS)}")
