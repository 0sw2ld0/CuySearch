"""Brave Search, por su página de resultados (sin clave).

Adaptado de `ddgs/engines/brave.py` (MIT, ver PROCEDENCIA.md). Con una clave
de la API oficial conviene más `brave_api`.
"""

from __future__ import annotations

import httpx

from cuysearch.html import analizar
from cuysearch.motores.base import Motor
from cuysearch.tipos import Consulta, Resultado

_PERIODOS = {"dia": "pd", "semana": "pw", "mes": "pm", "año": "py"}


class Brave(Motor):
    nombre = "brave"
    url = "https://search.brave.com/search"

    async def buscar(self, cliente: httpx.AsyncClient, consulta: Consulta) -> list[Resultado]:
        parametros = {"q": consulta.con_filtros_de_sitio(), "source": "web"}
        if consulta.periodo:
            parametros["tf"] = _PERIODOS[consulta.periodo]
        respuesta = await self._pedir(cliente, "GET", self.url, params=parametros)
        return self.leer(respuesta.text)

    def leer(self, html: str) -> list[Resultado]:
        resultados = []
        for item in analizar(html).buscar("div", data_type="web"):
            enlace = next((a for a in item.buscar("a") if a.primero("div", clase_parcial="title")), None)
            if enlace is None:
                continue
            titulos = enlace.buscar("div", clase_parcial="title")
            fragmento = next(
                (c for s in item.buscar("div", clase_parcial="snippet") for c in s.buscar("div", clase_parcial="content")),
                None,
            )
            resultado = self._resultado(
                titulos[-1].texto(), enlace.atributo("href"), fragmento.texto() if fragmento else ""
            )
            if resultado:
                resultados.append(resultado)
        return resultados
