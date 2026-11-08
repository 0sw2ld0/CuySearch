"""DuckDuckGo, por su versión HTML sin JavaScript.

Adaptado de `ddgs/engines/duckduckgo.py` (MIT, ver PROCEDENCIA.md).
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from cuysearch.html import analizar
from cuysearch.motores.base import Motor, MotorBloqueado
from cuysearch.tipos import Consulta, Resultado

_PERIODOS = {"dia": "d", "semana": "w", "mes": "m", "año": "y"}


def _url_real(href: str) -> str:
    """DuckDuckGo a veces envuelve el enlace en //duckduckgo.com/l/?uddg=…"""
    if href.startswith("//"):
        href = "https:" + href
    partes = urlparse(href)
    if partes.hostname and partes.hostname.endswith("duckduckgo.com") and partes.path.startswith("/l/"):
        return parse_qs(partes.query).get("uddg", [""])[0]
    return href


class DuckDuckGo(Motor):
    nombre = "duckduckgo"
    url = "https://html.duckduckgo.com/html/"

    async def buscar(self, cliente: httpx.AsyncClient, consulta: Consulta) -> list[Resultado]:
        datos = {"q": consulta.con_filtros_de_sitio(), "b": ""}
        if consulta.periodo:
            datos["df"] = _PERIODOS[consulta.periodo]
        respuesta = await self._pedir(cliente, "POST", self.url, data=datos)
        return self.leer(respuesta.status_code, respuesta.text)

    def leer(self, estado: int, html: str) -> list[Resultado]:
        # Cuando limita, responde 202 con una página de «anomalía» en vez de resultados.
        if estado == 202 or "anomaly-modal" in html:
            raise MotorBloqueado("duckduckgo pidió una comprobación anti-bots")
        resultados = []
        for cuerpo in analizar(html).buscar("div", "result__body"):
            enlace = cuerpo.primero("a", "result__a")
            if enlace is None:
                continue
            href = _url_real(enlace.atributo("href"))
            if href.startswith("https://duckduckgo.com/y.js?"):  # anuncio
                continue
            fragmento = cuerpo.primero(clase="result__snippet")
            resultado = self._resultado(enlace.texto(), href, fragmento.texto() if fragmento else "")
            if resultado:
                resultados.append(resultado)
        return resultados
