"""Motores con API oficial: SearXNG propio y servicios con clave del usuario.

Ninguno se usa sin que el usuario dé su URL o su clave. La clave viaja sólo en
la cabecera de la petición a ese servicio y nunca aparece en los avisos.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import httpx

from cuysearch.motores.base import ErrorDeMotor, Motor
from cuysearch.tipos import Consulta, Resultado

_DIAS = {"dia": 1, "semana": 7, "mes": 31, "año": 365}
_PERIODO_EN = {"dia": "day", "semana": "week", "mes": "month", "año": "year"}


def _lista(datos: object, *claves: str) -> list[dict]:
    for clave in claves:
        datos = datos.get(clave) if isinstance(datos, dict) else None
    return [d for d in datos if isinstance(d, dict)] if isinstance(datos, list) else []


class SearXNG(Motor):
    """Una instancia de SearXNG del usuario (puede vivir en localhost)."""

    nombre = "searxng"
    necesita_configuracion = True

    def __init__(self, url: str, tiempo: float = 15.0) -> None:
        super().__init__(tiempo)
        partes = urlparse(url or "")
        if partes.scheme not in ("http", "https") or not partes.hostname:
            raise ValueError("La URL de SearXNG debe ser http o https")
        if partes.username or partes.password:
            raise ValueError("La URL de SearXNG no puede llevar credenciales")
        self.url = url.rstrip("/")

    async def buscar(self, cliente: httpx.AsyncClient, consulta: Consulta) -> list[Resultado]:
        parametros = {
            "q": consulta.con_filtros_de_sitio(),
            "format": "json",
            "categories": "news" if consulta.noticias else "general",
            "language": consulta.idioma or "all",
            "pageno": "1",
        }
        if consulta.periodo:
            parametros["time_range"] = _PERIODO_EN[consulta.periodo]
        respuesta = await self._pedir(cliente, "GET", urljoin(self.url + "/", "search"), params=parametros,
                                      headers={"Accept": "application/json"})
        datos = self._json(respuesta)
        if not isinstance(datos, dict) or not isinstance(datos.get("results"), list):
            raise ErrorDeMotor("searxng devolvió un formato inesperado (¿falta `json` en search.formats?)")
        return [r for d in _lista(datos, "results")
                if (r := self._resultado(str(d.get("title") or ""), str(d.get("url") or ""),
                                         str(d.get("content") or ""),
                                         d.get("publishedDate") or d.get("published_date")))]


class Ollama(Motor):
    """Ollama Web Search, con la clave de ollama.com del usuario."""

    nombre = "ollama"
    necesita_configuracion = True
    url = "https://ollama.com/api/web_search"

    def __init__(self, clave: str, tiempo: float = 20.0) -> None:
        super().__init__(tiempo)
        if not clave:
            raise ValueError("Ollama Web Search necesita OLLAMA_API_KEY")
        self._clave = clave

    async def buscar(self, cliente: httpx.AsyncClient, consulta: Consulta) -> list[Resultado]:
        cuerpo = {"query": consulta.con_filtros_de_sitio(), "max_results": min(consulta.max_resultados, 10)}
        respuesta = await self._pedir(cliente, "POST", self.url, json=cuerpo,
                                      headers={"Authorization": f"Bearer {self._clave}"})
        return [r for d in _lista(self._json(respuesta), "results")
                if (r := self._resultado(str(d.get("title") or ""), str(d.get("url") or ""),
                                         str(d.get("content") or "")[:1000]))]


class BraveAPI(Motor):
    """Brave Search API oficial, con la clave del usuario."""

    nombre = "brave_api"
    necesita_configuracion = True
    url = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, clave: str, tiempo: float = 15.0) -> None:
        super().__init__(tiempo)
        if not clave:
            raise ValueError("Brave Search API necesita BRAVE_API_KEY")
        self._clave = clave

    async def buscar(self, cliente: httpx.AsyncClient, consulta: Consulta) -> list[Resultado]:
        parametros = {"q": consulta.con_filtros_de_sitio(), "count": str(min(consulta.max_resultados, 20))}
        if consulta.periodo:
            parametros["freshness"] = {"dia": "pd", "semana": "pw", "mes": "pm", "año": "py"}[consulta.periodo]
        respuesta = await self._pedir(cliente, "GET", self.url, params=parametros,
                                      headers={"X-Subscription-Token": self._clave, "Accept": "application/json"})
        return [r for d in _lista(self._json(respuesta), "web", "results")
                if (r := self._resultado(str(d.get("title") or ""), str(d.get("url") or ""),
                                         str(d.get("description") or ""), d.get("page_age")))]


class Tavily(Motor):
    nombre = "tavily"
    necesita_configuracion = True
    url = "https://api.tavily.com/search"

    def __init__(self, clave: str, tiempo: float = 20.0) -> None:
        super().__init__(tiempo)
        if not clave:
            raise ValueError("Tavily necesita TAVILY_API_KEY")
        self._clave = clave

    async def buscar(self, cliente: httpx.AsyncClient, consulta: Consulta) -> list[Resultado]:
        cuerpo: dict = {"query": consulta.texto, "max_results": min(consulta.max_resultados, 20),
                        "topic": "news" if consulta.noticias else "general"}
        if consulta.dominios:
            cuerpo["include_domains"] = list(consulta.dominios)
        if consulta.excluir:
            cuerpo["exclude_domains"] = list(consulta.excluir)
        if consulta.periodo:
            cuerpo["time_range"] = _PERIODO_EN[consulta.periodo]
        respuesta = await self._pedir(cliente, "POST", self.url, json=cuerpo,
                                      headers={"Authorization": f"Bearer {self._clave}"})
        return [r for d in _lista(self._json(respuesta), "results")
                if (r := self._resultado(str(d.get("title") or ""), str(d.get("url") or ""),
                                         str(d.get("content") or ""), d.get("published_date")))]


class Exa(Motor):
    nombre = "exa"
    necesita_configuracion = True
    url = "https://api.exa.ai/search"

    def __init__(self, clave: str, tiempo: float = 20.0) -> None:
        super().__init__(tiempo)
        if not clave:
            raise ValueError("Exa necesita EXA_API_KEY")
        self._clave = clave

    async def buscar(self, cliente: httpx.AsyncClient, consulta: Consulta) -> list[Resultado]:
        cuerpo: dict = {"query": consulta.texto, "numResults": min(consulta.max_resultados, 20),
                        "type": "auto", "contents": {"highlights": True}}
        if consulta.dominios:
            cuerpo["includeDomains"] = list(consulta.dominios)
        if consulta.excluir:
            cuerpo["excludeDomains"] = list(consulta.excluir)
        if consulta.periodo:
            desde = datetime.now(timezone.utc) - timedelta(days=_DIAS[consulta.periodo])
            cuerpo["startPublishedDate"] = desde.isoformat(timespec="seconds").replace("+00:00", "Z")
        respuesta = await self._pedir(cliente, "POST", self.url, json=cuerpo, headers={"x-api-key": self._clave})
        resultados = []
        for d in _lista(self._json(respuesta), "results"):
            destacados = d.get("highlights") if isinstance(d.get("highlights"), list) else []
            fragmento = " … ".join(str(h) for h in destacados[:3]) or str(d.get("text") or "")[:600]
            if r := self._resultado(str(d.get("title") or ""), str(d.get("url") or ""), fragmento,
                                    d.get("publishedDate")):
                resultados.append(r)
        return resultados
