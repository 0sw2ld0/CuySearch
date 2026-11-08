"""Bing, por su página de resultados.

Adaptado de `ddgs/engines/bing.py` (MIT, ver PROCEDENCIA.md).
"""

from __future__ import annotations

import base64
import binascii
import time
from urllib.parse import parse_qs, urlparse

import httpx

from cuysearch.html import analizar
from cuysearch.motores.base import Motor, MotorBloqueado
from cuysearch.tipos import Consulta, Resultado


def desenvolver_url(url: str) -> str:
    """Bing envuelve el destino en /ck/a?…&u=a1<base64>; aquí se recupera."""
    if not url.startswith("https://www.bing.com/ck/a?"):
        return url
    valores = parse_qs(urlparse(url).query).get("u", [])
    if not valores or len(valores[0]) <= 2:
        return url
    cifrado = valores[0][2:]
    try:
        return base64.urlsafe_b64decode(cifrado + "=" * (-len(cifrado) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return url


class Bing(Motor):
    nombre = "bing"
    url = "https://www.bing.com/search"

    async def buscar(self, cliente: httpx.AsyncClient, consulta: Consulta) -> list[Resultado]:
        texto = consulta.con_filtros_de_sitio()
        parametros = {"q": texto, "pq": texto}
        parametros["setlang"] = consulta.idioma or "en"
        if consulta.periodo:
            dia = int(time.time() // 86400)
            codigo = (f"ez5_{dia - 365}_{dia}" if consulta.periodo == "año"
                      else "ez" + {"dia": "1", "semana": "2", "mes": "3"}[consulta.periodo])
            parametros["filters"] = f'ex1:"{codigo}"'
        idioma = consulta.idioma or "en"
        respuesta = await self._pedir(cliente, "GET", self.url, params=parametros, follow_redirects=True,
                                      headers={"Accept-Language": f"{idioma},en;q=0.8"})
        if "/turing/captcha" in str(respuesta.url):
            raise MotorBloqueado("bing pidió un captcha")
        return self.leer(respuesta.text)

    def leer(self, html: str) -> list[Resultado]:
        if 'id="b_captcha' in html:
            raise MotorBloqueado("bing pidió un captcha")
        resultados = []
        for item in analizar(html).buscar("li", "b_algo"):
            titulo = item.primero("h2")
            enlace = titulo.primero("a") if titulo else None
            if enlace is None:
                continue
            href = enlace.atributo("href")
            if href.startswith("https://www.bing.com/aclick?"):  # anuncio
                continue
            fragmento = item.primero("p")
            resultado = self._resultado(enlace.texto(), desenvolver_url(href), fragmento.texto() if fragmento else "")
            if resultado:
                resultados.append(resultado)
        return resultados
