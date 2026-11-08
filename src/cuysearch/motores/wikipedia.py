"""Wikipedia, por su API oficial (MediaWiki `list=search`).

La idea viene de `ddgs/engines/wikipedia.py` (MIT, ver PROCEDENCIA.md), pero
aquí basta una petición: `list=search` ya devuelve título y fragmento.
"""

from __future__ import annotations

from urllib.parse import quote

import httpx

from cuysearch.motores.base import ErrorDeMotor, Motor
from cuysearch.tipos import Consulta, Resultado
from cuysearch.utiles import en_dominios


class Wikipedia(Motor):
    nombre = "wikipedia"

    def __init__(self, tiempo: float = 10.0, idioma: str = "en") -> None:
        super().__init__(tiempo)
        self.idioma = idioma

    async def buscar(self, cliente: httpx.AsyncClient, consulta: Consulta) -> list[Resultado]:
        dominio = f"{self._idioma(consulta)}.wikipedia.org"
        if consulta.dominios and not en_dominios(f"https://{dominio}/", consulta.dominios):
            return []
        if consulta.excluir and en_dominios(f"https://{dominio}/", consulta.excluir):
            return []
        parametros = {
            "action": "query",
            "list": "search",
            "srsearch": consulta.texto,
            "srlimit": str(min(consulta.max_resultados, 20)),
            "srprop": "snippet|timestamp",
            "format": "json",
            "utf8": "1",
        }
        respuesta = await self._pedir(cliente, "GET", f"https://{dominio}/w/api.php", params=parametros)
        return self.leer(self._json(respuesta), dominio)

    def _idioma(self, consulta: Consulta) -> str:
        idioma = (consulta.idioma or self.idioma or "en").split("-")[0].lower()
        return idioma if idioma.isalpha() and len(idioma) <= 3 else "en"

    def leer(self, datos: object, dominio: str) -> list[Resultado]:
        try:
            paginas = datos["query"]["search"]  # type: ignore[index]
        except (KeyError, TypeError) as exc:
            raise ErrorDeMotor("wikipedia devolvió un formato inesperado") from exc
        resultados = []
        for pagina in paginas:
            titulo = str(pagina.get("title") or "")
            if not titulo:
                continue
            url = f"https://{dominio}/wiki/" + quote(titulo.replace(" ", "_"))
            resultado = self._resultado(titulo, url, str(pagina.get("snippet") or ""), pagina.get("timestamp"))
            if resultado:
                resultados.append(resultado)
        return resultados
