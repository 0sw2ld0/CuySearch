"""Contrato común de los motores de búsqueda."""

from __future__ import annotations

from typing import ClassVar

import httpx

from cuysearch.tipos import Consulta, Resultado
from cuysearch.utiles import limpiar_texto, url_publica

USER_AGENT = "CuySearch/0.1 (+https://github.com/0sw2ld0/CuySearch)"


class ErrorDeMotor(RuntimeError):
    """El motor respondió algo inesperado o no respondió."""


class MotorBloqueado(ErrorDeMotor):
    """El motor limitó o bloqueó la petición (429, 403, captcha).

    CuySearch nunca intenta resolver un captcha ni hacerse pasar por un
    navegador: deja descansar ese motor y pasa al siguiente.
    """


class Motor:
    nombre: ClassVar[str]
    # Si necesita una clave o una URL propia del usuario.
    necesita_configuracion: ClassVar[bool] = False

    def __init__(self, tiempo: float = 10.0) -> None:
        self.tiempo = tiempo

    async def buscar(self, cliente: httpx.AsyncClient, consulta: Consulta) -> list[Resultado]:
        raise NotImplementedError

    async def _pedir(self, cliente: httpx.AsyncClient, metodo: str, url: str, **kwargs) -> httpx.Response:
        cabeceras = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
        try:
            respuesta = await cliente.request(metodo, url, headers=cabeceras, timeout=self.tiempo, **kwargs)
        except httpx.TimeoutException as exc:
            raise ErrorDeMotor(f"{self.nombre} tardó más de {self.tiempo:g} s") from exc
        except httpx.HTTPError as exc:
            raise ErrorDeMotor(f"{self.nombre} no responde ({type(exc).__name__})") from exc
        if respuesta.status_code in (403, 429):
            raise MotorBloqueado(f"{self.nombre} limitó la petición (HTTP {respuesta.status_code})")
        if respuesta.status_code in (401,):
            raise ErrorDeMotor(f"{self.nombre} rechazó la clave (HTTP 401)")
        if respuesta.status_code >= 400:
            raise ErrorDeMotor(f"{self.nombre} devolvió HTTP {respuesta.status_code}")
        return respuesta

    def _json(self, respuesta: httpx.Response) -> object:
        try:
            return respuesta.json()
        except ValueError as exc:
            raise ErrorDeMotor(f"{self.nombre} devolvió un JSON ilegible") from exc

    def _resultado(self, titulo: str, url: str, fragmento: str = "", fecha: str | None = None) -> Resultado | None:
        url = (url or "").strip()
        if not url_publica(url):
            return None
        return Resultado(
            titulo=limpiar_texto(titulo) or url,
            url=url,
            fragmento=limpiar_texto(fragmento),
            motor=self.nombre,
            fecha=fecha or None,
        )
