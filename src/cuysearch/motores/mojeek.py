"""Mojeek, buscador con índice propio.

Adaptado de `ddgs/engines/mojeek.py` (MIT, ver PROCEDENCIA.md).
"""

from __future__ import annotations

import httpx

from cuysearch.html import analizar
from cuysearch.motores.base import Motor, MotorBloqueado
from cuysearch.tipos import Consulta, Resultado


class Mojeek(Motor):
    nombre = "mojeek"
    url = "https://www.mojeek.com/search"

    async def buscar(self, cliente: httpx.AsyncClient, consulta: Consulta) -> list[Resultado]:
        parametros = {"q": consulta.con_filtros_de_sitio()}
        if consulta.idioma:
            parametros["lb"] = consulta.idioma
        respuesta = await self._pedir(cliente, "GET", self.url, params=parametros)
        return self.leer(respuesta.text)

    def leer(self, html: str) -> list[Resultado]:
        arbol = analizar(html)
        titulo = arbol.primero("title")
        if titulo is not None and "captcha" in titulo.texto().lower():
            raise MotorBloqueado("mojeek pidió un captcha")
        resultados = []
        for lista in arbol.buscar("ul", clase_parcial="results"):
            for item in lista.buscar("li"):
                cabecera = item.primero("h2")
                enlace = cabecera.primero("a") if cabecera else None
                if enlace is None:
                    continue
                fragmento = item.primero("p", "s")
                resultado = self._resultado(
                    cabecera.texto(), enlace.atributo("href"), fragmento.texto() if fragmento else ""
                )
                if resultado:
                    resultados.append(resultado)
        return resultados
